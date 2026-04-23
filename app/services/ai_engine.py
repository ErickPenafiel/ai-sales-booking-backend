from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import PromptTemplate
from langchain_ollama import ChatOllama, OllamaEmbeddings
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from app.services import agent_tools
from app.services import tracing

try:
    from langchain_groq import ChatGroq
except Exception:  # pragma: no cover
    ChatGroq = None

logger = logging.getLogger(__name__)


INFO_PRIORITY_KEYWORDS = (
    "cancelar",
    "cancelacion",
    "cancelación",
    "precio",
    "cuesta",
    "politica",
    "política",
    "donde",
    "dónde",
    "ubicacion",
    "ubicación",
    "direccion",
    "dirección",
)

BOOKING_KEYWORDS = (
    "turno",
    "horario",
    "reservar",
    "cita",
    "disponible",
    "cupo",
    "agendar",
)

BOOKING_OPTIONS_KEYWORDS = (
    "otro horario",
    "otros horarios",
    "otra opcion",
    "otra opción",
    "alternativa",
    "alternativas",
    "disponible",
    "disponibilidad",
    "opciones",
    "cambiar",
    "cancelar",
)

SAFE_FALLBACK_RESPONSE: dict[str, Any] = {
    "answer": "No pude procesar tu solicitud en este momento. Por favor intenta nuevamente.",
    "intent": "INFO",
    "extracted_entities": {
        "provider_id": None,
        "service_id": None,
        "date": None,
        "time": None,
        "customer_name": None,
        "customer_ci": None,
    },
}


ROUTER_PROMPT = PromptTemplate.from_template(
    """
Eres un Router de intenciones para un sistema de reservas.
Clasifica SOLO en una intención: BOOKING o INFO.

Reglas:
- BOOKING: consultar horarios, disponibilidad, agenda, turnos, reservar cita.
- INFO: políticas, servicios, ubicación, precios, cancelaciones y dudas generales.

Mensaje: {user_message}
Responde JSON estricto: {{"intent":"BOOKING|INFO"}}
""".strip()
)


ENTITY_EXTRACTION_PROMPT = PromptTemplate.from_template(
    """
Extrae entidades para booking desde el mensaje.
Si un campo no existe, responde null.
No inventes datos.

Reglas criticas:
- Prioriza SIEMPRE el ultimo mensaje del usuario sobre el historial.
- Si el ultimo mensaje pide nuevas opciones/alternativas/cancelacion, devuelve "time": null.
- HOY ES: {current_date} ({current_weekday}). Usa esta referencia para resolver "hoy" y "mañana".
- Si el mensaje actual es corto o fragmentado (solo numeros/CI), asume que completa datos pendientes del flujo previo.

Historial reciente (si existe):
--- CHAT HISTORY ---
{chat_history}

--- CURRENT USER MESSAGE ---
Mensaje: {user_message}

Responde JSON estricto:
{{
  "provider_id": string|null,
  "service_id": string|null,
  "date": "YYYY-MM-DD"|null,
  "time": "HH:MM"|null,
  "customer_name": string|null,
  "customer_ci": string|null
}}
""".strip()
)


BOOKING_EXECUTOR_PROMPT = PromptTemplate.from_template(
    """
Eres un asistente de reservas con FLUJO DE ESTADOS OBLIGATORIO.

MÁQUINA DE ESTADOS - SIGUE ESTA SECUENCIA ESTRICTA:
============================================================

🔵 ESTADO 1: DESCUBRIMIENTO (provider y service)
   CUANDO: No tienes provider_id O service_id
   ACCIÓN:
   - Llama get_providers_and_services para ver opciones
   - Presenta un resumen atractivo de providers y servicios
   - PREGUNTA: "¿Con qué profesional deseas atenderse?" Y "¿Qué servicio busca?"
   - Espera respuesta del usuario
   RESULTADO ESPERADO: provider_id + service_id

🟡 ESTADO 2: HORARIOS (slots disponibles)
   CUANDO: Tienes provider_id Y service_id, pero NO tienes date/time
   ACCIÓN:
   - NUNCA preguntes por provider o service de nuevo
   - Solo pregunta por fecha
   - Llama get_provider_slots con provider_id, service_id, y fecha
   - Presenta horarios disponibles como opciones
   RESULTADO ESPERADO: date + time

🟢 ESTADO 3: CIERRE (datos del cliente)
   CUANDO: Tienes provider_id, service_id, date, Y time
   ACCIÓN:
   - NUNCA preguntes por horarios de nuevo
   - Pide SOLO: nombre completo y CI/identificación
   - Ejecuta create_booking INMEDIATAMENTE
   RESULTADO ESPERADO: booking_id

============================================================

REGLAS CRÍTICAS ABSOLUTAS:
1. PROHIBIDO llamar get_provider_slots sin tener provider_id Y service_id completos
2. PROHIBIDO llamar create_booking sin tener provider_id, service_id, date, Y time
3. Si el usuario pide "horarios" o "disponibilidad" sin haber elegido provider y service:
   - Responde: "Primero necesito saber con quién y qué servicio deseas. ¿Me indicas qué profesional prefieres y qué tipo de consulta necesitas?"
4. Si el usuario quiere "reservar" sin haber seleccionado horario:
   - Responde: "¿Para qué día te gustaría el turno?"
5. Solo muestra horarios para UNA fecha específica a la vez

REGLAS DE EXTRACCIÓN:
- customer_name: UNICAMENTE nombre y apellido, sin texto adicional. Si no estás seguro, usa null.
- customer_ci: Solo el número de identificación sin texto. Si no estás seguro, usa null.
- time: SIEMPRE en formato HH:MM

EJEMPLO DE FLUJO CORRECTO:
---
Usuario: "Quiero reservar una consulta"
IA: *llama get_providers_and_services*
"Tenemos disponibles:
1. Dr. García - Consulta General (30min), Corte de cabello (45min)
2. Dra. López - Limpieza dental (60min)

¿Con quién deseas atenderse y qué servicio buscas?"
    
Usuario: "Dr. García, consulta general"
IA: "Con el Dr. García. ¿Para qué día te conviene? (Hoy o mañana)"

Usuario: "Mañana"
IA: *llama get_provider_slots(provider_id, service_id, fecha=manana)*
"Tienes disponible: 09:00, 10:30, 15:00. ¿Cuál prefieres?"

Usuario: "09:00"
IA: "Perfecto. Necesito tu nombre completo y CI para confirmar la reserva."

Usuario: "Juan Pérez, mi CI es 12345678"
IA: *llama create_booking*
"¡Listo Juan! Tu cita con el Dr. García está confirmada para mañana a las 09:00 (Consulta General, 30min). Te esperamos."

--- CHAT HISTORY ---
{chat_history}

--- CURRENT USER MESSAGE ---
{user_message}
""".strip()
)



RAG_PROMPT = PromptTemplate.from_template(
    """
Eres un sub-agente RAG stateless para un tenant SaaS.
Usa EXCLUSIVAMENTE el contexto provisto.
Si falta información, dilo claramente.

Contexto tenant:
{tenant_context}

Historial reciente:
--- CHAT HISTORY ---
{chat_history}

--- CURRENT USER MESSAGE ---
Mensaje usuario:
{user_message}

--- MEDIA ATTACHMENTS ---
{media_attachments}

Instrucciones adicionales:
- Si media_attachments contiene archivos, DEBES incluir un campo "attachments" en tu JSON de respuesta.
- El campo attachments debe ser un array de objetos con: url, type, caption.
- Esto permite que WhatsApp envíe las imágenes/videos al usuario.

Devuelve JSON estricto con este contrato:
{{
  "answer": string,
  "intent": "INFO",
  "extracted_entities": {{
    "provider_id": null,
    "date": null,
    "time": null,
    "customer_name": null,
    "customer_ci": null
  }},
  "attachments": array|null
}}
""".strip()
)


QUERY_REWRITE_PROMPT = PromptTemplate.from_template(
    """
Eres un asistente de reescritura de consultas para un sistema RAG.

Historial de conversación:
{chat_history}

Pregunta actual del usuario:
{user_message}

Instrucciones:
- Si la pregunta es autocontenida (no depende de contexto previo), devuélvela igual.
- Si hay contexto en el historial relevante (temas, entidades mencionadas), incorpóralo.
- Devuelve UNA SOLA pregunta reformulada que capture el contexto completo.
- No inventes información; solo expande la pregunta con contexto del historial.

Responde SOLO con la pregunta reformulada (sin explicaciones).
""".strip()
)


@dataclass
class AIEngineConfig:
    llm_provider: str = field(default="ollama")
    embedding_provider: str = field(default="qdrant")

    ollama_base_url: str = field(default="http://localhost:11434")
    ollama_model: str = field(default="llama3.2:latest")
    ollama_temperature: float = field(default=0.0)
    ollama_embedding_model: str = field(default="nomic-embed-text")

    groq_api_key: Optional[str] = field(default=None)
    groq_model: str = field(default="llama-3.1-8b-instant")
    groq_temperature: float = field(default=0.0)

    qdrant_url: str = field(default="http://localhost:6333")
    qdrant_api_key: Optional[str] = field(default=None)
    qdrant_collection: str = field(default="tenant_knowledge")
    qdrant_top_k: int = field(default=10)
    qdrant_embedding_model: str = field(default="sentence-transformers/all-MiniLM-L6-v2")
    qdrant_cloud_inference: bool = field(default=True)
    qdrant_check_compatibility: bool = field(default=False)

    def __post_init__(self) -> None:
        self.llm_provider = os.getenv("LLM_PROVIDER", self.llm_provider).strip().lower()
        self.embedding_provider = os.getenv("EMBEDDING_PROVIDER", self.embedding_provider).strip().lower()

        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", self.ollama_base_url)
        self.ollama_model = os.getenv("OLLAMA_CHAT_MODEL", os.getenv("OLLAMA_MODEL", self.ollama_model))
        self.ollama_embedding_model = os.getenv(
            "OLLAMA_EMBED_MODEL", os.getenv("OLLAMA_EMBEDDING_MODEL", self.ollama_embedding_model)
        )
        self.groq_api_key = os.getenv("GROQ_API_KEY", self.groq_api_key)
        self.groq_model = os.getenv("GROQ_MODEL", self.groq_model)

        try:
            self.ollama_temperature = float(os.getenv("OLLAMA_TEMPERATURE", str(self.ollama_temperature)))
        except Exception:
            self.ollama_temperature = 0.0

        try:
            self.groq_temperature = float(os.getenv("GROQ_TEMPERATURE", str(self.groq_temperature)))
        except Exception:
            self.groq_temperature = 0.0

        self.qdrant_url = os.getenv("QDRANT_URL", self.qdrant_url)
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY", self.qdrant_api_key)
        self.qdrant_collection = os.getenv("QDRANT_COLLECTION", self.qdrant_collection)
        self.qdrant_embedding_model = os.getenv("QDRANT_EMBEDDING_MODEL", self.qdrant_embedding_model)

        try:
            self.qdrant_top_k = int(os.getenv("QDRANT_TOP_K", str(self.qdrant_top_k)))
        except Exception:
            self.qdrant_top_k = 4

        self.qdrant_cloud_inference = os.getenv("QDRANT_CLOUD_INFERENCE", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.qdrant_check_compatibility = os.getenv("QDRANT_CHECK_COMPATIBILITY", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }


class AIOrchestrator:
    """Micro-arquitectura stateless Router + Executors para IA multi-tenant."""

    def __init__(self, config: AIEngineConfig | None = None) -> None:
        self.config = config or AIEngineConfig()
        self._llm = self._build_llm()
        self._booking_use_function_calling = os.getenv("BOOKING_USE_FUNCTION_CALLING", "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        try:
            self._tool_loop_max_steps = int(os.getenv("BOOKING_TOOL_LOOP_MAX_STEPS", "4"))
        except Exception:
            self._tool_loop_max_steps = 4

        self._llm_with_tools = None
        if self._booking_use_function_calling:
            try:
                self._llm_with_tools = self._llm.bind_tools(
                    [
                        agent_tools.get_providers_and_services,
                        agent_tools.get_provider_slots,
                        agent_tools.create_booking,
                        agent_tools.search_business_knowledge,
                    ]
                )
            except Exception:
                logger.warning("Function calling setup failed, fallback to stateless booking executor")

        self._embeddings: OllamaEmbeddings | None = None

        if self.config.embedding_provider == "ollama":
            self._embeddings = OllamaEmbeddings(
                model=self.config.ollama_embedding_model,
                base_url=self.config.ollama_base_url,
            )

        self._qdrant = AsyncQdrantClient(
            url=self.config.qdrant_url,
            api_key=self.config.qdrant_api_key,
            cloud_inference=self.config.qdrant_cloud_inference,
            check_compatibility=self.config.qdrant_check_compatibility,
        )

    def _build_llm(self) -> BaseChatModel:
        if self.config.llm_provider == "groq":
            if ChatGroq is None:
                raise RuntimeError("LLM_PROVIDER=groq requiere langchain-groq")
            if not self.config.groq_api_key:
                raise RuntimeError("LLM_PROVIDER=groq requiere GROQ_API_KEY")
            return ChatGroq(
                model=self.config.groq_model,
                temperature=self.config.groq_temperature,
                api_key=self.config.groq_api_key,
            )

        return ChatOllama(
            model=self.config.ollama_model,
            base_url=self.config.ollama_base_url,
            temperature=self.config.ollama_temperature,
        )

    @tracing.langsmith_traceable(run_type="chain", name="answer_customer")
    async def answer_customer(
        self,
        *,
        tenant_id: UUID,
        user_message: str,
        customer_phone: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not user_message.strip():
            return self._normalize_output(
                {
                    "answer": "Comparte tu consulta para ayudarte.",
                    "intent": "INFO",
                    "extracted_entities": self._empty_entities(),
                }
            )

        try:
            intent = await self._route_intent_stateless(user_message=user_message)
            tracing.record_trace({"kind": "orchestrator", "stage": "intent", "intent": intent, "tenant_id": str(tenant_id)})
            if intent == "BOOKING":
                result = await self.run_agent_tools_conversation(
                    tenant_id=tenant_id,
                    user_message=user_message,
                    customer_phone=customer_phone,
                    chat_history=chat_history,
                )
            else:
                result = await self._rag_executor_stateless(
                    tenant_id=tenant_id,
                    user_message=user_message,
                    chat_history=chat_history,
                )
            return self._normalize_output(result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("AIOrchestrator failed tenant=%s error=%s", tenant_id, exc)
            return SAFE_FALLBACK_RESPONSE.copy()

    async def run_agent_tools_conversation(
        self,
        *,
        tenant_id: UUID,
        user_message: str,
        customer_phone: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        logger.info("[BookingExecutor] dispatch tenant=%s", tenant_id)
        if self._booking_use_function_calling and self._llm_with_tools is not None:
            return await self._booking_executor_function_calling(
                tenant_id=tenant_id,
                user_message=user_message,
                customer_phone=customer_phone,
                chat_history=chat_history,
            )
        return await self._booking_executor_stateless(
            tenant_id=tenant_id,
            user_message=user_message,
            customer_phone=customer_phone,
            chat_history=chat_history,
        )

    @tracing.langsmith_traceable(run_type="chain", name="route_intent")
    async def _route_intent_stateless(self, *, user_message: str) -> str:
        # Fast path: avoid expensive LLM route when heuristics are sufficient.
        if self._contains_info_priority_keywords(user_message):
            return "INFO"
        if any(keyword in user_message.lower() for keyword in BOOKING_KEYWORDS):
            return "BOOKING"

        try:
            prompt = ROUTER_PROMPT.format(user_message=user_message)
            tracing.record_trace({"kind": "llm", "operation": "route_intent", "stage": "start", "user_message": user_message})
            start = datetime.utcnow()
            raw = await self._llm.ainvoke(prompt)
            duration = (datetime.utcnow() - start).total_seconds()
            payload = self._to_json_dict(raw)
            tracing.record_trace({"kind": "llm", "operation": "route_intent", "stage": "end", "duration_s": duration})
            intent = str(payload.get("intent", "")).upper()
            if intent in {"BOOKING", "INFO"}:
                # Guard anti-falso-positivo post LLM.
                if intent == "BOOKING" and self._contains_info_priority_keywords(user_message):
                    return "INFO"
                return intent
        except Exception as exc:
            logger.warning("[Router] fallback classifier due to error=%s", exc)

        return self.fallback_intent_classifier(user_message)

    @tracing.langsmith_traceable(run_type="chain", name="booking_executor_function_calling")
    async def _booking_executor_function_calling(
        self,
        *,
        tenant_id: UUID,
        user_message: str,
        customer_phone: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        tenant_str = str(tenant_id)
        current_date, current_weekday = self._get_current_date_context()

        entities = self._extract_entities_from_message(user_message)
        fragment_entities = self._extract_fragment_entities(user_message)
        for key, value in fragment_entities.items():
            if entities.get(key) is None and value is not None:
                entities[key] = value

        history_entities = self._extract_entities_from_history(chat_history)
        for key in ("provider_id", "service_id", "date", "time", "customer_name", "customer_ci"):
            if entities.get(key) is None and history_entities.get(key) is not None:
                entities[key] = history_entities.get(key)

        system_prompt = (
            "Eres un asistente de reservas con FLUJO DE ESTADOS OBLIGATORIO. "
            "SOLO puedes avanzar en este orden: 1)Provider+Service -> 2)Date+Time -> 3)CustomerData -> create_booking. "
            "PROHIBIDO buscar horarios sin provider_id Y service_id. "
            "PROHIBIDO confirmar reserva sin todos los campos. "
            'Solo devuelve JSON: {"answer": string, "intent": "BOOKING_IN_PROGRESS|BOOKING_CONFIRMED", '
            '"extracted_entities": {"provider_id": string|null, "service_id": string|null, "date": string|null, '
            '"time": string|null, "customer_name": string|null, "customer_ci": string|null}}.'
        )

        human_payload = {
            "tenant_id": tenant_str,
            "current_date": current_date,
            "current_weekday": current_weekday,
            "customer_phone": customer_phone,
            "user_message": user_message,
            "history": self._history_to_text(chat_history),
            "known_entities": entities,
        }

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=json.dumps(human_payload, ensure_ascii=False)),
        ]

        for _ in range(max(1, self._tool_loop_max_steps)):
            tracing.record_trace({"kind": "llm", "operation": "booking_fc_invoke", "stage": "start", "tenant_id": tenant_str})
            started = datetime.utcnow()
            ai_msg = await self._llm_with_tools.ainvoke(messages)
            tracing.record_trace(
                {
                    "kind": "llm",
                    "operation": "booking_fc_invoke",
                    "stage": "end",
                    "tenant_id": tenant_str,
                    "duration_s": (datetime.utcnow() - started).total_seconds(),
                }
            )

            tool_calls = getattr(ai_msg, "tool_calls", None) or []
            if not tool_calls:
                payload = self._to_json_dict(ai_msg)
                if not payload:
                    answer = self._raw_to_text(ai_msg)
                    payload = {
                        "answer": answer or "No pude completar la reserva. Intenta nuevamente.",
                        "intent": "BOOKING_IN_PROGRESS",
                        "extracted_entities": entities,
                    }
                if "extracted_entities" not in payload or not isinstance(payload.get("extracted_entities"), dict):
                    payload["extracted_entities"] = entities
                return payload

            messages.append(ai_msg)

            for call in tool_calls:
                tool_name = str(call.get("name", "")).strip()
                tool_args = call.get("args") or {}
                tool_call_id = call.get("id")

                tool_output = await self._execute_fc_tool_call(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    tenant_id=tenant_str,
                    customer_phone=customer_phone,
                )
                messages.append(ToolMessage(content=tool_output, tool_call_id=tool_call_id))

        # Safety fallback if model loops too much
        return {
            "answer": "Estoy procesando tu reserva, pero necesito que confirmes profesional y horario para continuar.",
            "intent": "BOOKING_IN_PROGRESS",
            "extracted_entities": entities,
        }

    async def _execute_fc_tool_call(
        self,
        *,
        tool_name: str,
        tool_args: dict[str, Any],
        tenant_id: str,
        customer_phone: str | None,
    ) -> str:
        try:
            if tool_name == "get_providers_and_services":
                return await self._call_tool_stateless(agent_tools.get_providers_and_services, tenant_id)

            if tool_name == "get_provider_slots":
                provider_id = tool_args.get("provider_id")
                service_id = tool_args.get("service_id")
                date_value = tool_args.get("date")
                if not provider_id or not service_id:
                    return json.dumps({"error": "missing_required_params", "message": "provider_id and service_id are required"})
                return await self._call_tool_stateless(
                    agent_tools.get_provider_slots,
                    tenant_id=tenant_id,
                    provider_id=str(provider_id),
                    service_id=str(service_id),
                    date=str(date_value),
                )

            if tool_name == "create_booking":
                provider_id = tool_args.get("provider_id")
                service_id = tool_args.get("service_id")
                if not provider_id or not service_id:
                    return json.dumps({"error": "missing_required_params", "message": "provider_id and service_id are required"})
                return await self._call_tool_stateless(
                    agent_tools.create_booking,
                    tenant_id=tenant_id,
                    provider_id=str(provider_id),
                    service_id=str(service_id),
                    date=str(tool_args.get("date")),
                    time=str(tool_args.get("time")),
                    customer_name=str(tool_args.get("customer_name") or ""),
                    customer_phone=(customer_phone or "").strip(),
                    customer_ci=str(tool_args.get("customer_ci") or ""),
                )

            return json.dumps({"error": "unknown_tool", "tool": tool_name})
        except Exception as exc:
            tracing.record_trace(
                {
                    "kind": "tool_call",
                    "stage": "error",
                    "tool": tool_name,
                    "error": str(exc),
                }
            )
            return json.dumps({"error": "tool_execution_failed", "tool": tool_name})

    @tracing.langsmith_traceable(run_type="chain", name="booking_executor")
    async def _booking_executor_stateless(
        self,
        *,
        tenant_id: UUID,
        user_message: str,
        customer_phone: str | None = None,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        tenant_str = str(tenant_id)
        current_date, current_weekday = self._get_current_date_context()
        current_entities = self._extract_entities_from_message(user_message)
        fragment_entities = self._extract_fragment_entities(user_message)
        for key, value in fragment_entities.items():
            if current_entities.get(key) is None and value is not None:
                current_entities[key] = value
        entities = dict(current_entities)

        # Prompt de control para el executor con contexto temporal inyectado.
        _ = BOOKING_EXECUTOR_PROMPT.format(
            current_date=current_date,
            current_weekday=current_weekday,
            chat_history=self._history_to_text(chat_history),
            user_message=user_message,
        )

        history_entities = self._extract_entities_from_history(chat_history)
        for key in (
            "provider_id",
            "date",
            "time",
            "customer_name",
            "customer_ci",
        ):
            if entities.get(key) is None and history_entities.get(key) is not None:
                entities[key] = history_entities.get(key)

        # Completa huecos con extractor LLM sin romper stateless.
        # IMPORTANT: Only use LLM for explicit entities, don't force-fill from context
        llm_entities = await self._extract_entities_via_llm(
            user_message,
            chat_history,
            current_date=current_date,
            current_weekday=current_weekday,
        )
        # Only merge LLM entities if they're explicitly mentioned in the user message
        # Don't overwrite with LLM guesses from context
        for key in (
            "provider_id",
            "date",
            "time",
        ):
            if entities.get(key) is None and llm_entities.get(key) is not None:
                entities[key] = llm_entities.get(key)

        # NEVER accept customer_name or customer_ci from LLM for initial requests
        # Only accept them when user explicitly provides them with clear indicators
        # This prevents LLM from injecting fake names like "Juan Pérez", "Paciente X", etc.

        if self._is_refresh_slots_request(user_message):
            # Reinicio de estado para evitar bucle de confirmacion previa.
            entities["time"] = None

        providers_payload = self._to_json_dict(
            await self._call_tool_stateless(agent_tools.get_providers_and_services, tenant_str)
        )
        providers = providers_payload.get("providers", []) if isinstance(providers_payload, dict) else []
        if not providers:
            return {
                "answer": "No se encontraron proveedores disponibles para este tenant.",
                "intent": "INFO",
                "extracted_entities": entities,
            }

        # Detect if user specified a provider
        user_specified_provider = self._user_specified_provider(providers=providers, user_message=user_message, entities=entities)

        # If no specific provider mentioned, show availability from ALL providers
        if not user_specified_provider:
            return await self._handle_multi_provider_availability(
                tenant_id=tenant_str,
                providers=providers,
                entities=entities,
                user_message=user_message,
                chat_history=chat_history,
            )

        selected_provider = self._select_provider(providers=providers, user_message=user_message, entities=entities)
        provider_id = str(selected_provider.get("id"))
        provider_name = str(selected_provider.get("name", "Especialista"))
        entities["provider_id"] = provider_id

        start_date = self._resolve_start_date(entities.get("date"), user_message)

        # Paso 2: cascada proactiva de hasta 3 días.
        slots_by_date: dict[str, list[str]] = {}
        for offset in range(3):
            current = (start_date + timedelta(days=offset)).isoformat()
            slots_payload = self._to_json_dict(
                await self._call_tool_stateless(
                    agent_tools.get_provider_slots,
                    tenant_id=tenant_str,
                    provider_id=provider_id,
                    date=current,
                )
            )
            slots = slots_payload.get("slots", []) if isinstance(slots_payload, dict) else []
            times = self._extract_times_from_slots(slots)
            if times:
                slots_by_date[current] = times

        if not slots_by_date:
            entities["date"] = start_date.isoformat()
            return {
                "answer": f"No encontré horarios con {provider_name} en los próximos 3 días.",
                "intent": "BOOKING_IN_PROGRESS",
                "extracted_entities": entities,
            }

        requested_time = self._normalize_time_hhmm(entities.get("time"))
        if requested_time is None:
            suggested_date = next(iter(slots_by_date.keys()))
            suggested_times = ", ".join(slots_by_date[suggested_date][:4])
            entities["date"] = suggested_date
            
            # Don't ask for customer data when just checking availability
            # Only prompt for name/CI when user explicitly wants to book
            return {
                "answer": (
                    f"Tengo disponibilidad con {provider_name} el {suggested_date} ({suggested_times}). "
                    "¿Qué horario prefieres? Indica el nombre del profesional si deseas agendar con otro."
                ),
                "intent": "BOOKING_IN_PROGRESS",
                "extracted_entities": entities,
            }

        entities["time"] = requested_time

        chosen_date = self._resolve_date_for_time(
            requested_date=entities.get("date"),
            requested_time=requested_time,
            slots_by_date=slots_by_date,
        )

        if chosen_date is None:
            fallback_date = next(iter(slots_by_date.keys()))
            available = ", ".join(slots_by_date[fallback_date][:5])
            entities["date"] = fallback_date
            return {
                "answer": (
                    f"No encontré el horario {requested_time}. "
                    f"El {fallback_date} tengo: {available}. Elige uno para continuar."
                ),
                "intent": "BOOKING_IN_PROGRESS",
                "extracted_entities": entities,
            }

        entities["date"] = chosen_date

        missing_fields = []
        if entities.get("customer_name") is None:
            missing_fields.append("nombre")
        if entities.get("customer_ci") is None:
            missing_fields.append("CI")
        if not (customer_phone and customer_phone.strip()):
            missing_fields.append("telefono")

        if missing_fields:
            return {
                "answer": (
                    f"Perfecto, tengo disponibilidad el {chosen_date} a las {requested_time} con {provider_name}. "
                    "Antes de confirmar compárteme: " + ", ".join(missing_fields) + "."
                ),
                "intent": "BOOKING_IN_PROGRESS",
                "extracted_entities": entities,
            }

        customer_name = str(entities["customer_name"]).strip()
        customer_ci = str(entities["customer_ci"]).strip()
        create_payload = self._to_json_dict(
            await self._call_tool_stateless(
                agent_tools.create_booking,
                tenant_id=tenant_str,
                provider_id=provider_id,
                date=chosen_date,
                time=requested_time,
                customer_name=customer_name,
                customer_phone=str(customer_phone).strip(),
                customer_ci=customer_ci,
            )
        )

        booking_id = create_payload.get("booking_id")
        if not booking_id:
            return {
                "answer": "No pude confirmar la reserva en este momento. Intenta nuevamente.",
                "intent": "BOOKING_IN_PROGRESS",
                "extracted_entities": entities,
            }

        return {
            "answer": (
                f"Listo {customer_name}. Tu cita con {provider_name} está confirmada para "
                f"el {chosen_date} a las {requested_time}. ¡Te esperamos!"
            ),
            "intent": "BOOKING_CONFIRMED",
            "extracted_entities": entities,
        }

    @tracing.langsmith_traceable(run_type="chain", name="rag_executor")
    async def _rag_executor_stateless(
        self,
        *,
        tenant_id: UUID,
        user_message: str,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        logger.info("[RAGExecutor] start tenant=%s", tenant_id)
        retrieve_start = datetime.utcnow()
        chunks, media_attachments = await self._retrieve_tenant_context(
            tenant_id=tenant_id, 
            query=user_message,
            chat_history=chat_history,
        )
        tracing.record_trace(
            {
                "kind": "rag",
                "stage": "retrieve_context",
                "tenant_id": str(tenant_id),
                "chunks_count": len(chunks),
                "media_count": len(media_attachments),
                "duration_s": (datetime.utcnow() - retrieve_start).total_seconds(),
            }
        )
        tenant_context = "\n\n".join(chunks) if chunks else "Sin contexto disponible para este tenant."
        history_text = self._history_to_text(chat_history)

        prompt = RAG_PROMPT.format(
            tenant_context=tenant_context,
            chat_history=history_text,
            user_message=user_message,
            media_attachments=json.dumps(media_attachments) if media_attachments else "[]",
        )
        tracing.record_trace({"kind": "llm", "operation": "rag_invoke", "stage": "start", "tenant_id": str(tenant_id), "user_message": user_message})
        start = datetime.utcnow()
        raw = await self._llm.ainvoke(prompt)
        duration = (datetime.utcnow() - start).total_seconds()
        tracing.record_trace({"kind": "llm", "operation": "rag_invoke", "stage": "end", "tenant_id": str(tenant_id), "duration_s": duration})
        payload = self._to_json_dict(raw)

        if not payload:
            return {
                "answer": "No tengo suficiente contexto para responder con certeza.",
                "intent": "INFO",
                "extracted_entities": self._empty_entities(),
            }

        if "extracted_entities" not in payload:
            payload["extracted_entities"] = self._empty_entities()

        if media_attachments and not payload.get("attachments"):
            payload["attachments"] = media_attachments

        return payload

    @tracing.langsmith_traceable(run_type="retriever", name="retrieve_tenant_context")
    async def _retrieve_tenant_context(
        self, 
        *, 
        tenant_id: UUID, 
        query: str,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        rewritten_query = await self._query_rewrite(query, chat_history)
        
        tenant_filter = qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="metadata.tenant_id",
                    match=qdrant_models.MatchValue(value=str(tenant_id)),
                )
            ]
        )

        points = await self._search_points(query=rewritten_query, tenant_filter=tenant_filter)
        
        reranked = await self._rerank_results(rewritten_query, points, top_k=3)
        
        out: list[str] = []
        media_attachments: list[dict[str, Any]] = []
        
        for point in reranked:
            payload = getattr(point, "payload", None) or {}
            text = self._payload_to_text(payload)
            if text:
                out.append(text)
            
            metadata = payload.get("metadata", {}) or {}
            if metadata.get("url"):
                media_attachments.append({
                    "url": metadata.get("url"),
                    "type": metadata.get("asset_type", "IMAGE"),
                    "caption": metadata.get("description", "") or metadata.get("title", ""),
                })
        
        return out, media_attachments

    async def _query_rewrite(
        self, 
        user_message: str,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> str:
        """Rewrite query using LLM with chat history context."""
        if not chat_history or len(chat_history) < 2:
            return user_message
            
        history_text = self._history_to_text(chat_history)
        
        try:
            prompt = QUERY_REWRITE_PROMPT.format(
                chat_history=history_text,
                user_message=user_message,
            )
            tracing.record_trace({
                "kind": "llm", 
                "operation": "query_rewrite", 
                "stage": "start"
            })
            start = datetime.utcnow()
            raw = await self._llm.ainvoke(prompt)
            duration = (datetime.utcnow() - start).total_seconds()
            tracing.record_trace({
                "kind": "llm", 
                "operation": "query_rewrite", 
                "stage": "end", 
                "duration_s": duration
            })
            
            rewritten = self._raw_to_text(raw).strip()
            if rewritten and len(rewritten) > 5:
                return rewritten
        except Exception as e:
            logger.debug(f"Query rewrite failed: {e}")
        
        return user_message

    async def _rerank_results(
        self, 
        query: str, 
        points: list[Any], 
        top_k: int = 3,
    ) -> list[Any]:
        """Rerank search results using algorithmic approach (BM25 + similarity)."""
        if not points or len(points) <= top_k:
            return points
        
        results = []
        for point in points:
            payload = getattr(point, "payload", None) or {}
            text = payload.get("text", payload.get("title", ""))
            results.append({
                "point": point,
                "text": text,
                "score": getattr(point, "score", 1.0),
            })
        
        try:
            from rank_bm25 import BM25Okapi
            import numpy as np
            
            texts = [r["text"] for r in results]
            if texts:
                bm25 = BM25Okapi([t.split() for t in texts])
                bm25_scores = bm25.get_scores(query.split())
                
                max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
                normalized_bm25 = [s / max_bm25 for s in bm25_scores]
                
                original_scores = [r["score"] for r in results]
                max_orig = max(original_scores) if max(original_scores) > 0 else 1.0
                normalized_orig = [s / max_orig for s in original_scores]
                
                alpha = 0.5
                combined_scores = [
                    alpha * normalized_bm25[i] + (1 - alpha) * normalized_orig[i]
                    for i in range(len(results))
                ]
                
                indexed_scores = list(enumerate(combined_scores))
                indexed_scores.sort(key=lambda x: x[1], reverse=True)
                
                reranked = [results[i[0]]["point"] for i in indexed_scores[:top_k]]
                return reranked
                
        except ImportError:
            logger.debug("rank_bm25 not available, using original scoring")
        
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        return [r["point"] for r in sorted_results[:top_k]]

    @tracing.langsmith_traceable(run_type="retriever", name="qdrant_search_points")
    async def _search_points(self, *, query: str, tenant_filter: qdrant_models.Filter) -> list[Any]:
        start = datetime.utcnow()
        if self.config.embedding_provider == "qdrant":
            try:
                result = await self._qdrant.query_points(
                    collection_name=self.config.qdrant_collection,
                    query=qdrant_models.Document(text=query, model=self.config.qdrant_embedding_model),
                    query_filter=tenant_filter,
                    limit=self.config.qdrant_top_k,
                    with_payload=True,
                )
                points = self._extract_points(result)
                tracing.record_trace(
                    {
                        "kind": "rag",
                        "stage": "qdrant_query_points",
                        "path": "cloud_inference",
                        "points_count": len(points),
                        "duration_s": (datetime.utcnow() - start).total_seconds(),
                    }
                )
                return points
            except Exception:
                logger.debug("Qdrant inference failed, fallback to local embeddings")
                tracing.record_trace(
                    {
                        "kind": "rag",
                        "stage": "qdrant_query_points",
                        "path": "cloud_inference_error",
                        "duration_s": (datetime.utcnow() - start).total_seconds(),
                    }
                )

        if self._embeddings is None:
            self._embeddings = OllamaEmbeddings(
                model=self.config.ollama_embedding_model,
                base_url=self.config.ollama_base_url,
            )

        vector = await self._embeddings.aembed_query(query)
        try:
            result = await self._qdrant.query_points(
                collection_name=self.config.qdrant_collection,
                query=vector,
                query_filter=tenant_filter,
                limit=self.config.qdrant_top_k,
                with_payload=True,
            )
            points = self._extract_points(result)
            tracing.record_trace(
                {
                    "kind": "rag",
                    "stage": "qdrant_query_points",
                    "path": "local_embeddings",
                    "points_count": len(points),
                    "duration_s": (datetime.utcnow() - start).total_seconds(),
                }
            )
            return points
        except Exception:
            tracing.record_trace(
                {
                    "kind": "rag",
                    "stage": "qdrant_query_points",
                    "path": "local_embeddings_error",
                    "duration_s": (datetime.utcnow() - start).total_seconds(),
                }
            )
            return []

    @tracing.langsmith_traceable(run_type="chain", name="extract_entities")
    async def _extract_entities_via_llm(
        self,
        user_message: str,
        chat_history: list[dict[str, Any]] | None = None,
        *,
        current_date: str,
        current_weekday: str,
    ) -> dict[str, Any]:
        try:
            prompt = ENTITY_EXTRACTION_PROMPT.format(
                user_message=user_message,
                chat_history=self._history_to_text(chat_history),
                current_date=current_date,
                current_weekday=current_weekday,
            )
            tracing.record_trace({"kind": "llm", "operation": "entity_extraction", "stage": "start", "user_message": user_message})
            start = datetime.utcnow()
            raw = await self._llm.ainvoke(prompt)
            duration = (datetime.utcnow() - start).total_seconds()
            tracing.record_trace({"kind": "llm", "operation": "entity_extraction", "stage": "end", "duration_s": duration})
            payload = self._to_json_dict(raw)
            if not payload:
                return self._empty_entities()

            out = self._empty_entities()
            out["provider_id"] = payload.get("provider_id")
            out["date"] = payload.get("date")
            out["time"] = self._normalize_time_hhmm(payload.get("time"))
            customer_name = payload.get("customer_name")
            out["customer_name"] = customer_name.strip() if isinstance(customer_name, str) and customer_name.strip() else None
            customer_ci = payload.get("customer_ci")
            out["customer_ci"] = customer_ci.strip() if isinstance(customer_ci, str) and customer_ci.strip() else None
            return out
        except Exception:
            return self._empty_entities()

    def _extract_entities_from_message(self, user_message: str) -> dict[str, Any]:
        entities = self._empty_entities()

        uuid_match = re.search(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b",
            user_message,
        )
        if uuid_match:
            entities["provider_id"] = uuid_match.group(0)

        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", user_message)
        if date_match:
            entities["date"] = date_match.group(1)

        # Match time in various formats: "09:00", "9:00", "900", "0900"
        time_match = re.search(r"\b(\d{1,2}):(\d{2})\b", user_message)
        if time_match:
            entities["time"] = self._normalize_time_hhmm(time_match.group(0))
        else:
            # Try matching without colon: "900" -> "09:00"
            time_match_alt = re.search(r"\b(\d{3,4})\b", user_message)
            if time_match_alt:
                time_str = time_match_alt.group(1)
                if len(time_str) == 3:
                    entities["time"] = self._normalize_time_hhmm(f"0{time_str[0]}:{time_str[1:]}")
                elif len(time_str) == 4:
                    entities["time"] = self._normalize_time_hhmm(f"{time_str[:2]}:{time_str[2:]}")

        # Patrones determinísticos para extraer el nombre del cliente.
        # IMPORTANT: Handle both explicit indicators AND direct name statements
        # Examples: "mi nombre es Diana", "Diana mi ci es...", "soy Juan, mi ci..."
        customer_patterns = [
            # "mi nombre es Juan Perez" or "me llamo Juan Perez"
            r"(?:mi nombre es|me llamo)\s+([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+){0,3})",
            # "a nombre de Diana Flores"
            r"a nombre de\s+([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+){0,3})",
            # "nombre: Juan Perez" or "nombre Juan Perez"
            r"(?:nombre|name)\s*[:=]\s*([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+){0,3})",
            # "Diana Rodriguez, mi ci es..." or "Diana Rodriguez mi ci es..." (name before "mi ci es")
            # Match words at start, but stop before "mi", "es", "el", etc.
            r"^([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+){0,4})\s*(?:,\s*)?(?:mi\s+)?ci\s+es\b",
            # "Juan Perez, ci 12345" (name followed by CI without "es")
            r"^([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+)*)\s*,\s*(?:mi\s+)?(?:ci|carnet|cedula)",
            # "soy Diana Rodriguez" (after other content like CI)
            r"(?:^|,\s*|\s+)\bsoy\s+([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+){0,3})",
            # "Diana Rodriguez, quiero/quisiera/necesito..." (name followed by booking request)
            r"^([A-ZÁÉÍÓÚ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚ][a-záéíóúñ]+){0,3})\s*,\s*(?:quiero|quisiera|necesito|deseo|me gustaria)",
        ]
        for pattern in customer_patterns:
            match = re.search(pattern, user_message)
            if match:
                candidate = match.group(1).strip()
                if len(candidate) >= 2:
                    # Clean up candidate - remove trailing Spanish words that shouldn't be part of name
                    # Common words that might be captured but aren't part of names
                    spanish_stop_words = ['mi', 'es', 'el', 'la', 'mi', 'tu', 'su', 'y', 'o', 'de', 'del', 'al']
                    words = candidate.split()
                    # Remove trailing stop words
                    while words and words[-1].lower() in spanish_stop_words:
                        words.pop()
                    candidate = ' '.join(words) if words else candidate
                    
                    # Additional validation: must look like a real name
                    if len(candidate) >= 2:
                        words = candidate.split()
                        if all(len(word) >= 2 for word in words):
                            # Exclude doctor/title words and common non-names
                            excluded_words = [
                                'doctor', 'doctora', 'dr', 'dra', 'licenciado', 'ingeniero', 'enfermera',
                                'quiero', 'quisiera', 'necesito', 'turno', 'cita', 'horario', 'reservar',
                                'agendar', 'disponible', 'verificar', 'consultar', 'saber', 'ver'
                            ]
                            if not any(word.lower() in excluded_words for word in words):
                                entities["customer_name"] = candidate
                                break

        # Captura CI robusta: reconoce frases como "mi ci es 12345678" o "CI: 12-345678"
        ci_match = re.search(
            r"(?:\bci\b|carnet|cedula|cédula|documento)\s*(?:es|:|-)?\s*([0-9]{5,20})",
            user_message,
            flags=re.IGNORECASE,
        )
        if ci_match:
            entities["customer_ci"] = ci_match.group(1).strip()

        return entities

    def _extract_fragment_entities(self, user_message: str) -> dict[str, Any]:
        entities = self._empty_entities()

        ci_token = re.search(r"\b\d{5,15}[A-Za-z]?\b", user_message)
        if ci_token:
            entities["customer_ci"] = ci_token.group(0)

        return entities

    def _extract_entities_from_history(self, chat_history: list[dict[str, Any]] | None) -> dict[str, Any]:
        entities = self._empty_entities()
        if not chat_history:
            return entities

        # Only extract from USER messages in history, not assistant responses
        for item in reversed(chat_history):
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "unknown")).strip().lower()
            
            # Skip assistant/bot responses - only extract from user messages
            if role in ("assistant", "bot", "ai", "system"):
                continue
            
            content = item.get("content")
            if not isinstance(content, str) or not content.strip():
                continue

            parsed = self._extract_entities_from_message(content)
            fragment_parsed = self._extract_fragment_entities(content)
            for key, value in fragment_parsed.items():
                if parsed.get(key) is None and value is not None:
                    parsed[key] = value
            for key in (
                "provider_id",
                "date",
                "time",
                "customer_name",
                "customer_ci",
            ):
                if entities.get(key) is None and parsed.get(key) is not None:
                    entities[key] = parsed.get(key)

            if all(entities.get(k) is not None for k in ("date", "time")):
                break

        return entities

    @staticmethod
    def _get_current_date_context() -> tuple[str, str]:
        now = datetime.now()
        return now.strftime("%Y-%m-%d"), now.strftime("%A")

    @staticmethod
    def _is_refresh_slots_request(user_message: str) -> bool:
        msg = user_message.lower()
        return any(keyword in msg for keyword in BOOKING_OPTIONS_KEYWORDS)

    @staticmethod
    def _history_to_text(chat_history: list[dict[str, Any]] | None) -> str:
        if not chat_history:
            return "Sin historial."

        lines: list[str] = []
        for item in chat_history[-10:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "unknown")).strip().lower()
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            lines.append(f"{role}: {content}")

        return "\n".join(lines) if lines else "Sin historial."

    @staticmethod
    def _resolve_start_date(explicit_date: Any, user_message: str) -> date:
        if isinstance(explicit_date, str):
            try:
                return date.fromisoformat(explicit_date)
            except Exception:
                pass

        msg = user_message.lower()
        if "mañana" in msg or "manana" in msg:
            return date.today() + timedelta(days=1)
        return date.today()

    @staticmethod
    def _extract_times_from_slots(slots: Any) -> list[str]:
        out: list[str] = []
        if not isinstance(slots, list):
            return out
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            start = slot.get("start")
            if not isinstance(start, str):
                continue
            parts = start.split("T")
            if len(parts) < 2:
                continue
            hhmm = parts[1][:5]
            if re.fullmatch(r"\d{2}:\d{2}", hhmm):
                out.append(hhmm)
        return out

    @staticmethod
    def _resolve_date_for_time(
        *,
        requested_date: Any,
        requested_time: str,
        slots_by_date: dict[str, list[str]],
    ) -> str | None:
        if isinstance(requested_date, str) and requested_date in slots_by_date:
            if requested_time in slots_by_date[requested_date]:
                return requested_date
            return None

        for candidate_date, times in slots_by_date.items():
            if requested_time in times:
                return candidate_date
        return None

    async def _handle_multi_provider_availability(
        self,
        *,
        tenant_id: str,
        resources: list[dict[str, Any]],
        entities: dict[str, Any],
        user_message: str,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Check availability across ALL resources and present combined options to user."""
        start_date = self._resolve_start_date(entities.get("date"), user_message)
        
        # Collect slots for ALL resources across next 3 days
        # Structure: { date: { provider_id: { provider_name, times: [] } } }
        availability_by_date: dict[str, dict[str, dict[str, Any]]] = {}
        
        for resource in resources:
            provider_id = str(resource.get("id"))
            provider_name = str(resource.get("name", "Especialista"))
            
            for offset in range(3):
                current_date = (start_date + timedelta(days=offset)).isoformat()
                
                try:
                    slots_payload = self._to_json_dict(
                        await self._call_tool_stateless(
                            agent_tools.get_provider_slots,
                            tenant_id=tenant_id,
                            provider_id=provider_id,
                            date=current_date,
                        )
                    )
                    slots = slots_payload.get("slots", []) if isinstance(slots_payload, dict) else []
                    times = self._extract_times_from_slots(slots)
                    
                    if times:
                        if current_date not in availability_by_date:
                            availability_by_date[current_date] = {}
                        
                        availability_by_date[current_date][provider_id] = {
                            "provider_name": provider_name,
                            "times": times,
                        }
                except Exception as e:
                    logger.warning(
                        f"Failed to get slots for resource {provider_name} on {current_date}: {e}"
                    )
                    continue
        
        if not availability_by_date:
            # No availability at all - provide helpful context
            day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            days_checked = []
            for offset in range(3):
                d = start_date + timedelta(days=offset)
                days_checked.append(f"{d.isoformat()} ({day_names[d.weekday()]})")
            
            provider_names = ", ".join([str(r.get("name", "Especialista")) for r in resources])
            return {
                "answer": (
                    f"No encontré horarios disponibles para ningún profesional en los próximos 3 días "
                    f"({', '.join(days_checked)}).\n\n"
                    f"Profesionales consultados: {provider_names}.\n\n"
                    "¿Deseas que verifique otra fecha o prefieres agendar con alguno de ellos en específico?"
                ),
                "intent": "BOOKING_IN_PROGRESS",
                "extracted_entities": entities,
            }
        
        # Build response showing all available doctors and their times
        response_parts = []
        response_parts.append("Estos son los horarios disponibles:")
        
        for date_str, resources_availability in availability_by_date.items():
            date_obj = datetime.fromisoformat(date_str).date()
            weekday_name = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][date_obj.weekday()]
            
            response_parts.append(f"\n📅 {date_str} ({weekday_name}):")
            
            for provider_id, res_data in resources_availability.items():
                provider_name = res_data["provider_name"]
                times = res_data["times"][:5]  # Show first 5 times
                times_str = ", ".join(times)
                response_parts.append(f"  • {provider_name}: {times_str}")
        
        response_parts.append("\n¿Con cuál profesional y horario deseas agendar tu cita?")
        response_parts.append("Indícame el nombre del profesional y el horario que prefieres.")
        
        full_response = "\n".join(response_parts)
        
        return {
            "answer": full_response,
            "intent": "BOOKING_IN_PROGRESS",
            "extracted_entities": entities,
        }

    @staticmethod
    def _user_specified_provider(providers: list[dict[str, Any]], user_message: str, entities: dict[str, Any]) -> bool:
        """Check if user explicitly specified a resource (doctor) in their message."""
        import unicodedata
        
        # Check if provider_id was extracted from message (UUID or from history/LLM)
        requested_provider_id = entities.get("provider_id")
        if isinstance(requested_provider_id, str):
            for res in resources:
                if str(res.get("id")) == requested_provider_id:
                    return True

        # Normalize message: remove accents for comparison
        message_lower = user_message.lower()
        message_normalized = unicodedata.normalize('NFD', message_lower)
        message_normalized = ''.join(c for c in message_normalized if unicodedata.category(c) != 'Mn')
        
        for res in resources:
            name = str(res.get("name", "")).strip()
            if not name:
                continue
            
            # Check multiple variations
            name_lower = name.lower()
            name_normalized = unicodedata.normalize('NFD', name_lower)
            name_normalized = ''.join(c for c in name_normalized if unicodedata.category(c) != 'Mn')
            
            # Check if resource name is in message (with and without accents)
            if name_lower in message_lower or name_normalized in message_normalized:
                return True
            
            # Check abbreviated forms: "dr." matches "doctor", "dra." matches "doctora"
            # Extract title and last name from resource name
            name_parts = name_lower.split()
            if len(name_parts) >= 2:
                title = name_parts[0].rstrip('.')
                last_name = name_parts[-1]
                
                # Check if user mentioned the title + last name
                if title in ['dr', 'dra', 'doctor', 'doctora', 'lic', 'ing']:
                    # Check various patterns
                    patterns_to_check = [
                        f"{title} {last_name}",
                        f"{title}. {last_name}",
                        f"doctor {last_name}" if title in ['dr'] else f"doctora {last_name}" if title in ['dra'] else None,
                        last_name,  # Just last name
                    ]
                    
                    for pattern in patterns_to_check:
                        if pattern and (pattern in message_lower or pattern in message_normalized):
                            return True
                    
                    # Also check normalized versions of last name
                    last_name_normalized = unicodedata.normalize('NFD', last_name)
                    last_name_normalized = ''.join(c for c in last_name_normalized if unicodedata.category(c) != 'Mn')
                    
                    if last_name_normalized in message_normalized:
                        return True
                else:
                    # No title, just check if name parts are in message
                    # Check full name without title
                    full_name_without_title = ' '.join(name_parts[1:])
                    if full_name_without_title in message_lower or full_name_without_title in message_normalized:
                        return True
                    # Check just last name
                    if last_name in message_lower or last_name in message_normalized:
                        return True

        return False

    @staticmethod
    def _select_provider(providers: list[dict[str, Any]], user_message: str, entities: dict[str, Any]) -> dict[str, Any]:
        import unicodedata
        
        requested_provider_id = entities.get("provider_id")
        if isinstance(requested_provider_id, str):
            for res in resources:
                if str(res.get("id")) == requested_provider_id:
                    return res

        # Use fuzzy matching to find the resource
        message_lower = user_message.lower()
        message_normalized = unicodedata.normalize('NFD', message_lower)
        message_normalized = ''.join(c for c in message_normalized if unicodedata.category(c) != 'Mn')
        
        for res in resources:
            name = str(res.get("name", "")).strip()
            if not name:
                continue
            
            name_lower = name.lower()
            name_normalized = unicodedata.normalize('NFD', name_lower)
            name_normalized = ''.join(c for c in name_normalized if unicodedata.category(c) != 'Mn')
            
            # Direct match
            if name_lower in message_lower or name_normalized in message_normalized:
                return res
            
            # Check by last name only
            name_parts = name_lower.split()
            if len(name_parts) >= 2:
                last_name = name_parts[-1]
                if last_name in message_lower or last_name in message_normalized:
                    return res
        
        # Fallback: return first resource
        return resources[0]

    @staticmethod
    def _contains_info_priority_keywords(user_message: str) -> bool:
        msg = user_message.lower()
        return any(keyword in msg for keyword in INFO_PRIORITY_KEYWORDS)

    @staticmethod
    def fallback_intent_classifier(user_message: str) -> str:
        msg = user_message.lower()
        if any(keyword in msg for keyword in INFO_PRIORITY_KEYWORDS):
            return "INFO"
        if any(keyword in msg for keyword in BOOKING_KEYWORDS):
            return "BOOKING"
        return "INFO"

    @staticmethod
    def extract_json_from_llm(text: str) -> dict[str, Any] | None:
        """Extract and parse the first JSON object from LLM output, ignoring extra text."""
        if not isinstance(text, str) or not text.strip():
            return None

        cleaned = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()
        match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if not match:
            return None

        try:
            parsed = json.loads(match.group(1))
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    @tracing.langsmith_traceable(run_type="tool", name="call_tool_stateless")
    async def _call_tool_stateless(self, tool_obj: Any, *args, **kwargs) -> Any:
        tool_name = getattr(tool_obj, "__name__", None) or getattr(tool_obj, "name", None) or str(tool_obj)
        start = datetime.utcnow()
        tracing.record_trace(
            {
                "kind": "tool_call",
                "tool": tool_name,
                "stage": "start",
                "args": args,
                "kwargs": kwargs,
            }
        )

        try:
            original = getattr(tool_obj, "func", None)
            if callable(original):
                res = await original(*args, **kwargs)
                tracing.record_trace(
                    {
                        "kind": "tool_call",
                        "tool": tool_name,
                        "stage": "end",
                        "duration_s": (datetime.utcnow() - start).total_seconds(),
                    }
                )
                return res

            coroutine = getattr(tool_obj, "coroutine", None)
            if callable(coroutine):
                res = await coroutine(*args, **kwargs)
                tracing.record_trace(
                    {
                        "kind": "tool_call",
                        "tool": tool_name,
                        "stage": "end",
                        "duration_s": (datetime.utcnow() - start).total_seconds(),
                    }
                )
                return res

            wrapped = getattr(tool_obj, "__wrapped__", None)
            if callable(wrapped):
                res = await wrapped(*args, **kwargs)
                tracing.record_trace(
                    {
                        "kind": "tool_call",
                        "tool": tool_name,
                        "stage": "end",
                        "duration_s": (datetime.utcnow() - start).total_seconds(),
                    }
                )
                return res

            if tool_obj is getattr(agent_tools, "list_available_providers", None):
                alias = getattr(agent_tools, "get_providers_and_services_func", None)
                if callable(alias):
                    res = await alias(*args, **kwargs)
                    tracing.record_trace(
                        {
                            "kind": "tool_call",
                            "tool": tool_name,
                            "stage": "end",
                            "duration_s": (datetime.utcnow() - start).total_seconds(),
                        }
                    )
                    return res

            if tool_obj is getattr(agent_tools, "get_provider_slots", None):
                alias = getattr(agent_tools, "get_provider_slots_func", None)
                if callable(alias):
                    res = await alias(*args, **kwargs)
                    tracing.record_trace(
                        {
                            "kind": "tool_call",
                            "tool": tool_name,
                            "stage": "end",
                            "duration_s": (datetime.utcnow() - start).total_seconds(),
                        }
                    )
                    return res

            if tool_obj is getattr(agent_tools, "create_booking", None):
                alias = getattr(agent_tools, "create_booking_func", None)
                if callable(alias):
                    res = await alias(*args, **kwargs)
                    tracing.record_trace(
                        {
                            "kind": "tool_call",
                            "tool": tool_name,
                            "stage": "end",
                            "duration_s": (datetime.utcnow() - start).total_seconds(),
                        }
                    )
                    return res

            if callable(tool_obj):
                result = tool_obj(*args, **kwargs)
                if hasattr(result, "__await__"):
                    res = await result
                    tracing.record_trace(
                        {
                            "kind": "tool_call",
                            "tool": tool_name,
                            "stage": "end",
                            "duration_s": (datetime.utcnow() - start).total_seconds(),
                        }
                    )
                    return res

                tracing.record_trace(
                    {
                        "kind": "tool_call",
                        "tool": tool_name,
                        "stage": "end",
                        "duration_s": (datetime.utcnow() - start).total_seconds(),
                    }
                )
                return result

            payload = kwargs if kwargs else (args[0] if len(args) == 1 else args)
            ainvoke = getattr(tool_obj, "ainvoke", None)
            if callable(ainvoke):
                res = await ainvoke(payload)
                tracing.record_trace(
                    {
                        "kind": "tool_call",
                        "tool": tool_name,
                        "stage": "end",
                        "duration_s": (datetime.utcnow() - start).total_seconds(),
                    }
                )
                return res

            invoke = getattr(tool_obj, "invoke", None)
            if callable(invoke):
                res = invoke(payload)
                tracing.record_trace(
                    {
                        "kind": "tool_call",
                        "tool": tool_name,
                        "stage": "end",
                        "duration_s": (datetime.utcnow() - start).total_seconds(),
                    }
                )
                return res

            raise RuntimeError("Tool original callable not found")

        except Exception as e:
            tracing.record_trace(
                {
                    "kind": "tool_call",
                    "tool": tool_name,
                    "stage": "error",
                    "duration_s": (datetime.utcnow() - start).total_seconds(),
                    "error": str(e),
                }
            )
            raise

    def _to_json_dict(self, raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw

        text = self._raw_to_text(raw)
        if not text:
            return {}

        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            pass

        parsed = self.extract_json_from_llm(text)
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _raw_to_text(raw: Any) -> str:
        if isinstance(raw, str):
            return raw
        content = getattr(raw, "content", None)
        if isinstance(content, str):
            return content
        return str(raw) if raw is not None else ""

    @staticmethod
    def _extract_points(result: Any) -> list[Any]:
        points = getattr(result, "points", None)
        if points is not None:
            return list(points)
        if isinstance(result, list):
            return result
        return []

    @staticmethod
    def _payload_to_text(payload: dict[str, Any]) -> str:
        for key in ("text", "content", "page_content", "document"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _normalize_time_hhmm(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
        if not match:
            return None

        hour = int(match.group(1))
        minute = int(match.group(2))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return None
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _empty_entities() -> dict[str, Any]:
        return {
            "provider_id": None,
            "date": None,
            "time": None,
            "customer_name": None,
            "customer_ci": None,
        }

    def _normalize_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return SAFE_FALLBACK_RESPONSE.copy()

        answer = payload.get("answer")
        intent = str(payload.get("intent", "INFO")).upper()
        entities_raw = payload.get("extracted_entities", {})

        if not isinstance(answer, str) or not answer.strip():
            return SAFE_FALLBACK_RESPONSE.copy()

        entities = self._empty_entities()
        if isinstance(entities_raw, dict):
            entities["provider_id"] = entities_raw.get("provider_id")
            entities["date"] = entities_raw.get("date")
            entities["time"] = self._normalize_time_hhmm(entities_raw.get("time")) if entities_raw.get("time") else None

            customer_name = entities_raw.get("customer_name")
            if isinstance(customer_name, str) and customer_name.strip():
                entities["customer_name"] = customer_name.strip()

            customer_ci = entities_raw.get("customer_ci")
            if isinstance(customer_ci, str) and customer_ci.strip():
                entities["customer_ci"] = customer_ci.strip()

        if isinstance(entities["date"], str):
            try:
                date.fromisoformat(entities["date"])
            except Exception:
                entities["date"] = None

        if not intent:
            intent = "INFO"

        return {
            "answer": answer.strip(),
            "intent": intent,
            "extracted_entities": entities,
        }

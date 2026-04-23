# CRUD Endpoints por Modulo

## Objetivo

Esta documentacion refleja la estructura actual de endpoints con rutas explicitas y separacion por modulos.

Base URL comun: `/api/v1`

---

## Estructura de Modulos

```text
app/api/v1/endpoints/
├── crud_tenants.py        # Modulo Tenants
├── crud_resources.py      # Modulo Resources
├── crud_customers.py      # Modulo Customers
├── crud_services.py       # Modulo Services
├── crud_availabilities.py # Modulo Availabilities
├── crud_appointments.py   # Modulo Appointments
├── crud_payments.py       # Modulo Payments
├── crud_media.py          # Modulo Media
├── crud_chat_messages.py  # Modulo Chat Messages
├── crud_stats.py          # Modulo Stats
├── crud_providers.py      # Modulo Providers (per-tenant providers)
└── crud_resource_context.py # Upload + index context into Qdrant
```

Registro central:

```python
# app/api/v1/router.py
api_router.include_router(tenants_router, prefix="/tenants", tags=["CRUD - Tenants"])
api_router.include_router(resources_router, tags=["CRUD - Resources"])
api_router.include_router(customers_router, tags=["CRUD - Customers"])
api_router.include_router(services_crud_router, tags=["CRUD - Services"])
api_router.include_router(availabilities_crud_router, tags=["CRUD - Availabilities"])
api_router.include_router(appointments_crud_router, tags=["CRUD - Appointments"])
api_router.include_router(payments_crud_router, tags=["CRUD - Payments"])
api_router.include_router(media_crud_router, tags=["CRUD - Media"])
api_router.include_router(chat_crud_router, tags=["CRUD - Chat"])
api_router.include_router(stats_crud_router, tags=["CRUD - Stats"])
```

Nota: el prefijo `/api/v1` se aplica una sola vez en `app/main.py`.

---

## Modulo Tenants

Archivo: `app/api/v1/endpoints/crud_tenants.py`

| Metodo | Endpoint                      | Descripcion       |
| ------ | ----------------------------- | ----------------- |
| POST   | `/api/v1/tenants/`            | Crear tenant      |
| GET    | `/api/v1/tenants/`            | Listar tenants    |
| GET    | `/api/v1/tenants/{tenant_id}` | Obtener tenant    |
| PUT    | `/api/v1/tenants/{tenant_id}` | Actualizar tenant |
| DELETE | `/api/v1/tenants/{tenant_id}` | Eliminar tenant   |

---

## Modulo Resources

Archivo: `app/api/v1/endpoints/crud_resources.py`

| Metodo | Endpoint                                | Descripcion         |
| ------ | --------------------------------------- | ------------------- |
| POST   | `/api/v1/tenants/{tenant_id}/resources` | Crear resource      |
| GET    | `/api/v1/resources/{resource_id}`       | Obtener resource    |
| GET    | `/api/v1/tenants/{tenant_id}/resources` | Listar resources    |
| PUT    | `/api/v1/resources/{resource_id}`       | Actualizar resource |
| DELETE | `/api/v1/resources/{resource_id}`       | Eliminar resource   |

---

## Modulo Customers

Archivo: `app/api/v1/endpoints/crud_customers.py`

| Metodo | Endpoint                                | Descripcion         |
| ------ | --------------------------------------- | ------------------- |
| POST   | `/api/v1/tenants/{tenant_id}/customers` | Crear customer      |
| GET    | `/api/v1/customers/{customer_id}`       | Obtener customer    |
| GET    | `/api/v1/tenants/{tenant_id}/customers` | Listar customers    |
| PUT    | `/api/v1/customers/{customer_id}`       | Actualizar customer |
| DELETE | `/api/v1/customers/{customer_id}`       | Eliminar customer   |

---

## Modulos ex CRUD - Other

Archivos:

- `app/api/v1/endpoints/crud_services.py`
- `app/api/v1/endpoints/crud_availabilities.py`
- `app/api/v1/endpoints/crud_appointments.py`
- `app/api/v1/endpoints/crud_payments.py`
- `app/api/v1/endpoints/crud_media.py`
- `app/api/v1/endpoints/crud_chat_messages.py`
- `app/api/v1/endpoints/crud_stats.py`

### Services

- POST `/api/v1/tenants/{tenant_id}/services`
- GET `/api/v1/services/{service_id}`
- GET `/api/v1/tenants/{tenant_id}/services`
- PUT `/api/v1/services/{service_id}`
- DELETE `/api/v1/services/{service_id}`

### Availability

- POST `/api/v1/tenants/{tenant_id}/availabilities`
- GET `/api/v1/availabilities/{availability_id}`
- GET `/api/v1/tenants/{tenant_id}/availabilities`
- PUT `/api/v1/availabilities/{availability_id}`
- DELETE `/api/v1/availabilities/{availability_id}`

### Appointments

- POST `/api/v1/tenants/{tenant_id}/appointments`
- GET `/api/v1/appointments/{appointment_id}`
- GET `/api/v1/tenants/{tenant_id}/appointments`
- PUT `/api/v1/appointments/{appointment_id}`
- POST `/api/v1/appointments/{appointment_id}/cancel`
- DELETE `/api/v1/appointments/{appointment_id}`

### Payments

- POST `/api/v1/tenants/{tenant_id}/payments`
- GET `/api/v1/payments/{payment_id}`
- GET `/api/v1/tenants/{tenant_id}/payments`
- PUT `/api/v1/payments/{payment_id}/status`
- DELETE `/api/v1/payments/{payment_id}`

### Media

- POST `/api/v1/tenants/{tenant_id}/media`
- GET `/api/v1/media/{media_id}`
- GET `/api/v1/tenants/{tenant_id}/media`
- PUT `/api/v1/media/{media_id}`
- DELETE `/api/v1/media/{media_id}`

### Chat

- POST `/api/v1/customers/{customer_id}/messages`
- GET `/api/v1/customers/{customer_id}/messages`
- DELETE `/api/v1/customers/{customer_id}/messages`

### Stats

- GET `/api/v1/stats/summary`
- GET `/api/v1/tenants/{tenant_id}/stats`

---

## Endpoints Obsoletos Eliminados

- Se elimino el modulo monolitico `app/api/v1/endpoints/crud.py`.
- Se elimino el modulo agrupado `app/api/v1/endpoints/crud_other.py`.
- Se elimino la documentacion legacy `scripts/CRUD_DOCUMENTATION.md`.

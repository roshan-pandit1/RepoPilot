Local infrastructure is defined in ../compose.yaml. PostgreSQL and Redis are internal-only;
API and web bind to loopback. The migrate service finishes before application processes start.
The dispatcher is a separate process of the same modular monolith, not a microservice.
No cloud infrastructure is provisioned by this repository.

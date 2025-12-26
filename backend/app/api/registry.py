from fastapi import APIRouter
import random
import time

router = APIRouter()

@router.get("/status")
def get_service_status():
    # Simulate service health checks
    services = [
        {"name": "Market Data Feed", "type": "External API", "status": "operational", "latency": f"{random.randint(20, 150)}ms"},
        {"name": "Order Execution System", "type": "Internal", "status": "operational", "latency": f"{random.randint(5, 20)}ms"},
        {"name": "Portfolio Analytics Engine", "type": "Compute", "status": "operational", "latency": f"{random.randint(50, 300)}ms"},
        {"name": "User Authentication", "type": "Security", "status": "operational", "latency": f"{random.randint(10, 50)}ms"},
        {"name": "Historical Data Store", "type": "Database", "status": "operational", "latency": f"{random.randint(10, 40)}ms"},
        {"name": "Risk Management Module", "type": "Compute", "status": "operational", "latency": f"{random.randint(30, 100)}ms"},
        {"name": "Notification Service", "type": "Messaging", "status": "operational", "latency": f"{random.randint(5, 15)}ms"},
    ]
    
    # Simulate a random degradation
    if random.random() < 0.1:
        degraded_service = random.choice(services)
        degraded_service["status"] = "degraded"
        degraded_service["latency"] = f"{random.randint(500, 2000)}ms"
        
    return {
        "timestamp": time.time(),
        "services": services,
        "system_status": "operational" if all(s["status"] == "operational" for s in services) else "degraded"
    }

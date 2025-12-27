"""
Script to check all registered routes in the FastAPI app
"""
from main import app

print("=" * 60)
print("🔍 ALL REGISTERED ROUTES")
print("=" * 60)

for route in app.routes:
    if hasattr(route, 'methods') and hasattr(route, 'path'):
        methods = ', '.join(route.methods)
        print(f"  {methods:20} {route.path}")
    elif hasattr(route, 'path'):
        print(f"  {'WEBSOCKET':20} {route.path}")

print("=" * 60)

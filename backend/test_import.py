"""
Test if routers import correctly
"""
try:
    print("Testing imports...")
    from routers import files, jobs
    print("✅ Files router imported successfully")
    print(f"   Files router prefix: {files.router.prefix}")
    print(f"   Files routes count: {len(files.router.routes)}")
    
    print("✅ Jobs router imported successfully")
    print(f"   Jobs router prefix: {jobs.router.prefix}")
    print(f"   Jobs routes count: {len(jobs.router.routes)}")
    
    print("\nJobs router paths:")
    for route in jobs.router.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            print(f"   {list(route.methods)} {route.path}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

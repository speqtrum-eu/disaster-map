from fastapi import Request, HTTPException


async def request_logger(request: Request):
    """Log incoming requests."""
    from starlette.middleware.base import BaseHTTPMiddleware
    
    class LoggingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            method = request.method
            url = str(request.url)
            
            response = await call_next(request)
            
            print(f"[{method}] {url} - Status: {response.status_code}")
            
            return response
    
    return LoggingMiddleware()


async def error_handler(request: Request, exc: Exception):
    """Handle errors gracefully."""
    from starlette.responses import JSONResponse
    
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": str(exc.detail)}
        )
    
    print(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
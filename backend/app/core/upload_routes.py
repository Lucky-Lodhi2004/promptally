from fastapi.routing import APIRoute
from backend.app.core.config import settings


class BoundedFormRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def bounded(request):
            if request.headers.get('content-type', '').lower().startswith('multipart/form-data'):
                async with request.form(max_files=settings.MAX_UPLOAD_FILES, max_fields=100):
                    return await original(request)
            return await original(request)

        return bounded

import base64
import hashlib
from core import logger
from core.config import config


def require_basic_auth(handler_class):
    def wrap_execute(handler_execute):
        async def _execute(self, transforms, *args, **kwargs):
            logger.debug(f"[AUTH] Request to {self.request.path} from {self.request.remote_ip}")
            logger.debug(f"[AUTH] Headers: {dict(self.request.headers)}")

            # Auth completely disabled in config
            if config.WEBAUTHUSER is False and config.WEBAUTHPASS is False:
                logger.debug("[AUTH] → Disabled in config (both user and pass False)")
                return await handler_execute(self, transforms, *args, **kwargs)

            if config.WEBAUTHUSER is False or config.WEBAUTHPASS is False:
                logger.debug("[AUTH] → Partially disabled (user or pass missing)")
                return await handler_execute(self, transforms, *args, **kwargs)

            auth_header = self.request.headers.get('Authorization')
            logger.debug(f"[AUTH] Authorization header: {auth_header}")

            if not auth_header or not auth_header.startswith('Basic '):
                logger.debug("[AUTH] → No Basic Auth header → 401")
                return await _send_401(self)

            try:
                # Decode
                auth_decoded = base64.b64decode(auth_header[6:]).decode('utf-8')
                username, password = auth_decoded.split(':', 1)
                logger.debug(f"[AUTH] Decoded user: {username}")

                # === FIXED: Compare plain text (matching your config) ===
                if username == config.WEBAUTHUSER and password == config.WEBAUTHPASS:
                    logger.debug("[AUTH] → SUCCESS")
                    return await handler_execute(self, transforms, *args, **kwargs)
                else:
                    logger.debug(f"[AUTH] → Wrong credentials → 401 (user={username})")
                    return await _send_401(self)

            except Exception as e:
                logger.debug(f"[AUTH] Exception during auth: {e}")
                return await _send_401(self)

        async def _send_401(self):
            logger.debug("[AUTH] Sending 401 response")
            self.set_status(401)
            self.set_header('WWW-Authenticate', 'Basic realm=AlarmServer')
            self.write({"error": "Unauthorized - Basic Auth required"})
            
            # CRITICAL FIX: Prevent Tornado TypeError
            if self._transforms is None:
                self._transforms = []
            
            self.finish()
            return None

        return _execute

    handler_class._execute = wrap_execute(handler_class._execute)
    return handler_class

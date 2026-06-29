"""Deprecated spider client placeholder.

Spider has moved into orchestration-backend as a business module, so JobCrawlService now calls
app.server.spider directly instead of calling capability-backend over HTTP.
"""


class CapabilitySpiderClient:
    """Deprecated placeholder kept only to avoid stale imports during local transition."""

    def __init__(self, *args, **kwargs):
        """Reject new instances because the HTTP spider client is no longer supported."""
        raise RuntimeError("CapabilitySpiderClient is deprecated; use app.server.spider.src.service.SpiderService.")

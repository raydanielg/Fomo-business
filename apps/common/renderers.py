from rest_framework.renderers import JSONRenderer


class FomoJSONRenderer(JSONRenderer):
    """
    Wraps non-paginated DRF responses in the standard envelope.

    Paginated list responses and error responses are already enveloped by the
    pagination class / exception handler, so we skip wrapping when the payload
    already contains an envelope key.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return super().render(data, accepted_media_type, renderer_context)

        if isinstance(data, dict) and ("success" in data or "error" in data):
            return super().render(data, accepted_media_type, renderer_context)

        wrapped = {"success": True, "data": data}
        return super().render(wrapped, accepted_media_type, renderer_context)

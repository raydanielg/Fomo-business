from django.urls import path

from .views import LegalAcceptView, LegalDocumentView

urlpatterns = [
    path("<str:doc_type>/", LegalDocumentView.as_view(), name="legal-document"),
    path("<str:doc_type>/accept/", LegalAcceptView.as_view(), name="legal-accept"),
]

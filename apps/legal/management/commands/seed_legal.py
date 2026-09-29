from datetime import date

from django.core.management.base import BaseCommand

from apps.legal.models import LegalDocument

TERMS = """## 1. Acceptance of Terms
By creating an account or using Fomo ("Your Business, Simplified."), you agree to these Terms of Service. If you do not agree, do not use the service.
## 2. About Fomo
Fomo is a business management platform that helps businesses manage sales, products, inventory, customers, expenses, invoices, payments, reports, staff, branches and related operations.
- Specific features vary by subscription plan, permissions, region and configuration.
## 3. Account Registration
You agree to:
- Provide accurate information when creating an account.
- Maintain the security of your account.
- Keep your login credentials private.
- Accept responsibility for activity performed through your account.
Notify Fomo immediately if you suspect unauthorized access.
## 4. Business Accounts
Users may create or join businesses within Fomo. Owners and administrators may manage members, roles, permissions, branches, business settings and subscriptions.
Access to business information depends on the permissions assigned to you.
## 5. User Roles and Permissions
Fomo supports roles such as Owner, Administrator, Manager, Cashier, Storekeeper, Accountant and Staff. Roles may differ between businesses.
- Permissions may limit what you can view, create, edit, delete, export or manage.
## 6. Subscription Plans
Some features are available only on specific subscription plans. Plans may determine access to reports, advanced analytics, exports, scheduled reports, branches, staff limits, storage and other capabilities.
The features available to you are determined by your active plan.
## 7. Billing and Payments
- Subscription fees apply per the current Fomo pricing information.
- Billing periods, renewals, upgrades, downgrades and cancellation follow the terms shown at purchase.
- Failed payments may result in restricted access after applicable notice.
## 8. Business Data
You remain responsible for the information you enter into Fomo, including products, sales, customers, expenses, invoices, staff information and business records.
- Ensure information you enter is accurate and lawful.
## 9. Financial Information
Fomo provides business management and record-keeping tools. Fomo is not a bank, accountant, tax authority, financial adviser or legal adviser.
You remain responsible for complying with applicable financial, tax and business requirements.
## 10. Acceptable Use
You must not use Fomo to:
- Violate applicable laws.
- Impersonate another person.
- Access another business without authorization.
- Bypass permissions or subscription restrictions.
- Abuse the API, attack the platform or interfere with service availability.
- Distribute malware or misuse customer information.
## 11. Intellectual Property
Fomo branding, the application interface, software, logos, trademarks, documentation and platform technology belong to Fomo and its licensors.
You retain appropriate rights to your own business content and data, subject to these Terms and applicable law.
## 12. Third-Party Services
Fomo may integrate with external services such as payment, SMS, email, messaging, cloud infrastructure and analytics providers. Third-party services have their own terms and privacy policies.
## 13. Service Availability
Fomo aims to provide reliable service. Availability may occasionally be affected by maintenance, infrastructure failures, network issues, third-party services, security incidents or circumstances outside reasonable control.
## 14. Suspension and Termination
Accounts may be suspended or terminated for serious violations, unauthorized access, abuse, fraudulent activity, unpaid subscriptions, security concerns or legal requirements.
## 15. Limitation of Liability
This section is a placeholder pending review by qualified legal counsel. To the maximum extent permitted by applicable law, Fomo's liability is limited as described in the applicable agreements.
## 16. Changes to the Service and Terms
Fomo may introduce new features, improvements and changes to functionality, plans and these Terms. Material changes will be communicated as required by applicable law. Continued use after applicable changes may constitute acceptance, subject to law.
## 17. Governing Law
Placeholder — to be configured based on the Fomo legal entity and legal advice before production release.
## 18. Contact Us
Questions about these Terms? Contact the Fomo support team:
- Email: support@fomo.co.tz
- Website: https://fomo.co.tz
"""

PRIVACY = """## 1. Overview
This Privacy Policy explains how Fomo ("Your Business, Simplified.") collects, uses and protects information when you use the platform.
## 2. Information We Collect
- Account information: name, email, phone number.
- Business information: business name, branches, staff roles.
- Business records you enter: sales, products, customers, expenses, invoices, payments.
- Technical information: device, app version, usage and diagnostic data.
## 3. How We Use Information
- To provide and operate Fomo features.
- To secure accounts and prevent abuse.
- To communicate service, subscription and security notices.
- To improve reliability and product quality.
## 4. Business and Tenant Data
Business data is isolated per business. Staff access is governed by roles and permissions set by the business owner or administrators.
## 5. Sharing
We do not sell your data. We may share limited data with service providers (hosting, messaging, payment processing) strictly to operate the service, or when required by law.
## 6. Data Retention
We retain data while your account is active and as needed for legal, accounting and security requirements. Deletion requests follow the applicable data-protection policy.
## 7. Security
We use industry-standard measures including encryption in transit, token-based authentication and access controls. No system is perfectly secure; report suspected incidents to us promptly.
## 8. Your Choices
You may update profile information, manage notification preferences and request account or data changes through the app or support.
## 9. Contact
Questions about privacy? Contact privacy@fomo.co.tz
"""


class Command(BaseCommand):
    help = "Seed v1.0 Terms of Service and Privacy Policy documents."

    def handle(self, *args, **kwargs):
        for doc_type, title, content in [
            ("terms", "Terms of Service", TERMS),
            ("privacy", "Privacy Policy", PRIVACY),
        ]:
            doc, created = LegalDocument.objects.update_or_create(
                doc_type=doc_type,
                version="1.0",
                defaults={
                    "title": title,
                    "content": content.strip(),
                    "effective_date": date.today(),
                    "is_current": True,
                    "requires_acceptance": True,
                },
            )
            doc.__class__.objects.filter(doc_type=doc_type).exclude(
                pk=doc.pk).update(is_current=False)
            self.stdout.write(f"{'created' if created else 'updated'}: {doc}")

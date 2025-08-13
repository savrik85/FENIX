import logging
from typing import Any

import openai

from ..config import settings


logger = logging.getLogger(__name__)


class AIService:
    """Service for AI-powered content generation using OpenAI API"""

    def __init__(self):
        self.client = None
        if settings.openai_api_key:
            self.client = openai.OpenAI(api_key=settings.openai_api_key)
        else:
            logger.warning("OpenAI API key not configured")

    async def generate_business_email(self, tender_data: dict[str, Any]) -> str:
        """
        Generate business email content responding to a tender opportunity

        Args:
            tender_data: Dictionary containing tender information

        Returns:
            Generated email content as string
        """
        if not self.client:
            logger.error("OpenAI client not initialized")
            return self._get_fallback_email(tender_data)

        try:
            # Prepare context from tender data
            context = self._prepare_tender_context(tender_data)

            # Generate AI response
            prompt = self._build_email_prompt(context)

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional business representative of "
                            "Dual Action Windows (DAW), which has been delivering "
                            "high-quality European windows to USA since 2013. "
                            "IMPORTANT COMPANY INFORMATION: "
                            "- Founded in 2013 by Petr Pechousek (software engineer) "
                            "- We specialize in Tilt & Turn windows from Europe to USA "
                            "- Our principles: CARE (customer and planet care), "
                            "AFFORDABLE QUALITY (high quality at affordable prices), "
                            "HONESTY (we keep our word), SPEED (fast responses) "
                            "- We offer energy-efficient windows that outperform "
                            "domestic products "
                            "- We operate remotely from Czech Republic "
                            "Write a professional business email in English responding "
                            "to a found public tender/RFP. The email should be polite, "
                            "specific, mention our values and USA experience, ask for "
                            "missing information needed for proposal preparation. "
                            "Do NOT suggest in-person meetings or site visits since "
                            "we operate remotely from Czech Republic."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=500,
                temperature=0.7,
            )

            generated_content = response.choices[0].message.content
            return generated_content.strip()

        except Exception as e:
            logger.error(f"Failed to generate AI email content: {str(e)}")
            return self._get_fallback_email(tender_data)

    def _prepare_tender_context(self, tender_data: dict[str, Any]) -> dict[str, Any]:
        """Extract and organize relevant information from tender data"""
        return {
            "title": tender_data.get("title", "Nezadáno"),
            "location": tender_data.get("location", "Nezadáno"),
            "estimated_value": tender_data.get("estimated_value"),
            "description": tender_data.get("description", ""),
            "contact_info": tender_data.get("contact_info", {}),
            "response_deadline": tender_data.get("response_deadline"),
            "source": tender_data.get("source", "Nezadáno"),
            "keywords_found": tender_data.get("keywords_found", []),
        }

    def _build_email_prompt(self, context: dict[str, Any]) -> str:
        """Build prompt for AI email generation"""
        prompt_parts = [
            "Nalezl jsem tuto veřejnou zakázku:",
            f"- Název: {context['title']}",
            f"- Lokalita: {context['location']}",
            f"- Zdroj: {context['source']}",
        ]

        if context["estimated_value"]:
            prompt_parts.append(
                f"- Odhadovaná hodnota: ${context['estimated_value']:,.0f}"
            )

        if context["description"]:
            description = (
                context["description"][:200] + "..."
                if len(context["description"]) > 200
                else context["description"]
            )
            prompt_parts.append(f"- Popis: {description}")

        if context["keywords_found"]:
            prompt_parts.append(
                f"- Klíčová slova: {', '.join(context['keywords_found'])}"
            )

        if context["response_deadline"]:
            prompt_parts.append(f"- Deadline: {context['response_deadline']}")

        prompt_parts.extend(
            [
                "",
                "Write a business email that:",
                "1. Politely greets and introduces Dual Action Windows (DAW)",
                "2. Specifically references this tender/RFP opportunity",
                "3. Mentions our experience since 2013 delivering European windows",
                "4. Emphasizes our principles: affordable quality, customer care",
                "5. Highlights energy efficiency and Tilt & Turn technology",
                "6. Requests additional technical information needed for proposal",
                "7. Suggests next steps (remote consultation, spec review)",
                "8. Professionally closes with contact information",
                "",
                "Email should be max 200 words, professional but friendly tone. "
                "IMPORTANT: Do NOT suggest in-person meetings or site visits.",
            ]
        )

        return "\n".join(prompt_parts)

    def _get_fallback_email(self, tender_data: dict[str, Any]) -> str:
        """Fallback email content when AI generation fails"""
        title = tender_data.get("title", "nabídky")
        location = tender_data.get("location", "")

        location_part = (
            f" v oblasti {location}" if location and location != "Nezadáno" else ""
        )

        return f"""
Dear Sir/Madam,

We would like to respond to your tender opportunity "{title}"{location_part}.

We are Dual Action Windows (DAW) - a company that has been successfully
delivering high-quality European windows and doors to the US market since 2013.
Our energy-efficient Tilt & Turn windows outperform domestic products in quality
while maintaining competitive pricing.

Our core principles include customer care, affordable quality, and fast
responses through process automation.

To prepare an accurate proposal, we would need the following information:

• Technical specifications for required windows/doors
• Dimensions and quantities of individual units
• Material and energy efficiency class requirements
• Project timeline and delivery requirements

We would be happy to schedule a remote consultation to review detailed
specifications and discuss your project requirements.

Best regards,
Dual Action Windows Team
""".strip()

    def get_missing_info_suggestions(self, tender_data: dict[str, Any]) -> list[str]:
        """Analyze tender data and suggest what information might be missing"""
        suggestions = []

        if not tender_data.get("estimated_value"):
            suggestions.append("Odhadovaná hodnota zakázky")

        if not tender_data.get("response_deadline"):
            suggestions.append("Termín pro podání nabídky")

        if not tender_data.get("contact_info", {}).get("email"):
            suggestions.append("Kontaktní email")

        if not tender_data.get("contact_info", {}).get("phone"):
            suggestions.append("Kontaktní telefon")

        if not tender_data.get("location") or tender_data.get("location") == "Nezadáno":
            suggestions.append("Přesná lokalita projektu")

        # Technical specifications that are typically missing
        suggestions.extend(
            [
                "Technické specifikace oken/dveří",
                "Rozměry a počty kusů",
                "Požadavky na materiál",
                "Energetická třída",
                "Termín realizace",
            ]
        )

        return suggestions

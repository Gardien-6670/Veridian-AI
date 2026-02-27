"""
Client Groq pour les appels IA
Gère les réponses, traductions et résumés de tickets
Support de 4 clés API avec fallback automatique
"""

import os
from groq import Groq
from loguru import logger
from bot.config import GROQ_MODEL_FAST, GROQ_MODEL_QUALITY, SYSTEM_PROMPT_SUPPORT, SYSTEM_PROMPT_TICKET_SUMMARY


class GroqClient:
    def __init__(self):
        """Initialise le client Groq avec 4 clés API."""
        self.api_keys = [
            os.getenv('GROQ_API_KEY_1'),
            os.getenv('GROQ_API_KEY_2'),
            os.getenv('GROQ_API_KEY_3'),
            os.getenv('GROQ_API_KEY_4')
        ]
        
        # Filtrer les clés vides
        self.api_keys = [key for key in self.api_keys if key]
        
        if not self.api_keys:
            logger.error("✗ Aucune clé Groq trouvée dans .env (GROQ_API_KEY_1-4)")
        else:
            logger.info(f"✓ Client Groq initialisé avec {len(self.api_keys)} clés API disponibles")
        
        self.current_key_index = 0
    
    def _get_client(self, force_key_index=None):
        """Retourne un client Groq avec la clé actuelle ou spécifique."""
        if force_key_index is not None:
            key_index = force_key_index
        else:
            key_index = self.current_key_index % len(self.api_keys) if self.api_keys else 0
        
        if not self.api_keys or key_index >= len(self.api_keys):
            return None
        
        return Groq(api_key=self.api_keys[key_index])

    def generate_support_response(self, message: str, guild_name: str, language: str = 'en') -> str:
        """Génère une réponse IA avec fallback sur 4 clés."""
        if not self.api_keys:
            return "Erreur: Aucune clé Groq disponible"
        
        system_prompt = SYSTEM_PROMPT_SUPPORT.format(guild_name=guild_name)
        
        for attempt in range(len(self.api_keys)):
            try:
                client = self._get_client(force_key_index=attempt)
                if not client:
                    continue
                
                completion = client.chat.completions.create(
                    model=GROQ_MODEL_FAST,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    temperature=0.7,
                    max_tokens=500,
                    top_p=1,
                    stream=False,
                )
                
                response = completion.choices[0].message.content
                logger.info(f"✓ Support généré (clé #{attempt + 1}, {len(response)} chars)")
                return response
                
            except Exception as e:
                logger.warning(f"⚠ Clé Groq #{attempt + 1} échouée: {str(e)[:100]}")
        
        logger.error("✗ Toutes les clés Groq épuisées")
        return "Je suis désolé, je n'ai pas pu traiter votre demande. Veuillez ouvrir un ticket."

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        """Traduit un texte avec fallback."""
        if not self.api_keys:
            return text
        
        system = (
            "You are a translation engine.\n"
            "Rules:\n"
            "- Translate strictly from the source language to the target language.\n"
            "- Output ONLY the translated text (no quotes, no explanations).\n"
            "- Preserve formatting, line breaks, emojis, mentions and code blocks.\n"
            "- Do not add or remove information.\n"
        )
        prompt = (
            f"Source language: {source_language}\n"
            f"Target language: {target_language}\n"
            "Text:\n"
            f"{text}"
        )
        
        for attempt in range(len(self.api_keys)):
            try:
                client = self._get_client(force_key_index=attempt)
                if not client:
                    continue
                
                completion = client.chat.completions.create(
                    model=GROQ_MODEL_FAST,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=1000,
                    stream=False,
                )
                
                logger.debug(f"✓ Traduction (clé #{attempt + 1})")
                return completion.choices[0].message.content.strip()
                
            except Exception as e:
                logger.warning(f"⚠ Clé Groq #{attempt + 1} traduction: {str(e)[:80]}")
        
        return text

    def generate_ticket_summary(self, messages: list, ticket_language: str) -> str:
        """Génère un résumé de ticket avec fallback."""
        if not self.api_keys:
            return "Impossible de générer le résumé"
        
        conversation = "\n".join([
            f"[{msg.get('author', 'Unknown')}]: {msg.get('content', '')}"
            for msg in messages
        ])
        
        system_prompt = SYSTEM_PROMPT_TICKET_SUMMARY.format(ticket_language=ticket_language)
        
        for attempt in range(len(self.api_keys)):
            try:
                client = self._get_client(force_key_index=attempt)
                if not client:
                    continue
                
                completion = client.chat.completions.create(
                    model=GROQ_MODEL_QUALITY,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Conversation:\n\n{conversation}"}
                    ],
                    temperature=0.5,
                    max_tokens=800,
                    stream=False,
                )
                
                logger.info(f"✓ Résumé (clé #{attempt + 1})")
                return completion.choices[0].message.content
                
            except Exception as e:
                logger.warning(f"⚠ Clé Groq #{attempt + 1} résumé: {str(e)[:80]}")
        
        return "Impossible de générer le résumé du ticket."

    def detect_question(self, message: str) -> bool:
        """Détecte si un message est une question."""
        question_indicators = ['?', 'comment', 'pourquoi', 'quoi', 'qu\'est', 'qui', 'où', 'quand', 'quel',
                             'how', 'why', 'what', 'who', 'where', 'when', 'which']
        
        if any(ind in message.lower() for ind in question_indicators):
            return True
        
        if len(message.split()) < 3:
            return False
        
        if not self.api_keys:
            return False
        
        try:
            client = self._get_client(force_key_index=0)
            if not client:
                return False
            
            completion = client.chat.completions.create(
                model=GROQ_MODEL_FAST,
                messages=[{"role": "user", "content": f"Question ou non? Réponds: oui/non.\n{message}"}],
                temperature=0.1,
                max_tokens=10,
                stream=False,
            )
            
            response = completion.choices[0].message.content.lower()
            return 'oui' in response or 'yes' in response
            
        except Exception:
            return False

"""
OpenVitality AI - Dynamic API Manager with PostgreSQL Integration
====================================================================
This module provides intelligent API management by storing all API
configurations in PostgreSQL and dynamically selecting the best API
for each task based on health, rate limits, and performance.
"""

import os
import asyncio
import time
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import asyncpg
import aiohttp
import yaml
from cryptography.fernet import Fernet
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class APIManager:
    """
    Central API management system that dynamically selects and uses APIs
    based on PostgreSQL configuration, health status, and rate limits.
    
    Think of this as your application's "API brain" - it knows about all
    available APIs, monitors their health, tracks usage, and automatically
    switches to backups when needed.
    """
    
    def __init__(self, db_url: str, encryption_key: Optional[str] = None):
        """
        Initialize the API Manager.
        
        Args:
            db_url: PostgreSQL connection string
                   Example: "postgresql://user:pass@localhost:5432/openvitality"
            encryption_key: Key for encrypting API credentials (generated if not provided)
        """
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None
        
        # Initialize encryption for API keys
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
        else:
            new_key_bytes = Fernet.generate_key()
            self.cipher = Fernet(new_key_bytes)
            logger.warning(
                "API_ENCRYPTION_KEY not found. Generated a new key. "
                "To persist credentials across restarts, add this to your .env file: "
                "API_ENCRYPTION_KEY=%s",
                new_key_bytes.decode('ascii')
            )
        
        # Cache for frequently accessed APIs (reduces DB queries)
        self._api_cache: Dict[str, Dict] = {}
        self._cache_ttl = 300  # 5 minutes
        
        # Session for HTTP requests
        self._http_session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """
        Initialize database connection pool and HTTP session.
        Call this before using the API manager.
        """
        # Create connection pool (10-20 connections is good for most apps)
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        
        # Create HTTP session for API calls
        self._http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        
        logger.info("API Manager initialized successfully")
    
    async def close(self):
        """Clean up resources."""
        if self.pool:
            await self.pool.close()
        if self._http_session:
            await self._http_session.close()
    
    # =========================================================================
    # DATABASE POPULATION
    # =========================================================================
    
    async def populate_from_yaml(self, yaml_file: str):
        """
        Load all APIs from the YAML database file and insert into PostgreSQL.
        
        This is like "teaching" the database about all available APIs.
        Run this once during setup or when you add new APIs.
        
        Args:
            yaml_file: Path to the YAML API database file
        """
        logger.info(f"Loading APIs from {yaml_file}...")
        
        with open(yaml_file, 'r') as f:
            api_data = yaml.safe_load(f)
        
        async with self.pool.acquire() as conn:
            # Start a transaction
            async with conn.transaction():
                # Process each category
                for category_name, category_data in api_data.items():
                    if not isinstance(category_data, dict):
                        continue
                    
                    # Skip metadata sections
                    if category_name in ['version', 'project', 'description', 
                                        'usage_guidelines', 'integration_examples',
                                        'deployment_configs', 'emergency_numbers']:
                        continue
                    
                    # Map category to our system categories
                    category_mapping = {
                        'speech_to_text': 'stt',
                        'text_to_speech': 'tts',
                        'llm_apis': 'llm',
                        'translation': 'translation',
                        'medical_knowledge': 'medical_knowledge',
                        'medical_terminology': 'medical_terminology',
                        'nlp_libraries': 'nlp',
                        'privacy_security': 'security',
                        'healthcare_standards': 'interoperability',
                        'regional_health': 'regional',
                        'emergency_location': 'location',
                        'vector_databases': 'vector_db',
                        'audio_processing': 'audio',
                        'telephony': 'telephony'
                    }
                    
                    mapped_category = category_mapping.get(category_name, category_name)
                    
                    # Insert each API in this category
                    for api_key, api_info in category_data.items():
                        if not isinstance(api_info, dict):
                            continue
                        
                        await self._insert_api(conn, api_key, api_info, mapped_category)
        
        logger.info("Database populated successfully!")
    
    async def _insert_api(self, conn, api_key: str, api_info: Dict, category: str):
        """Helper method to insert a single API into the database."""
        
        # Extract information with safe defaults
        name = api_info.get('name', api_key)
        description = api_info.get('description', '')
        base_url = api_info.get('base_url', '')
        documentation = api_info.get('documentation', api_info.get('documentation_url', ''))
        
        # Authentication
        auth_type = api_info.get('authentication', 'none')
        if auth_type in ['None', 'none', 'None (public access)', 'None (self-hosted)', 
                        'None (library)']:
            auth_type = 'none'
            requires_auth = False
        elif 'API key' in auth_type or 'api key' in auth_type.lower():
            auth_type = 'api_key'
            requires_auth = True
        elif 'OAuth' in auth_type:
            auth_type = 'oauth2'
            requires_auth = True
        else:
            requires_auth = 'key' in auth_type.lower() or 'token' in auth_type.lower()
        
        # Rate limits - parse from text
        rate_limit_text = api_info.get('rate_limit', '')
        rate_limits = self._parse_rate_limits(rate_limit_text)
        
        # Cost
        cost = api_info.get('cost', 'Free')
        cost_type = 'free' if 'free' in cost.lower() else 'freemium' if 'tier' in cost.lower() else 'paid'
        
        # Languages (for STT/TTS)
        languages = api_info.get('languages', api_info.get('supported_languages', []))
        if isinstance(languages, str):
            if '+' in languages:
                # "120+" -> extract all possible language codes
                languages = self._get_common_language_codes()
            else:
                languages = [languages]
        
        # Determine priority based on cost and description
        priority = 50  # Default
        if cost_type == 'free' and 'unlimited' in rate_limit_text.lower():
            priority = 10  # Highest priority
        elif cost_type == 'free':
            priority = 20
        elif 'PRIMARY' in description.upper() or 'primary' in api_info.get('use_cases', []):
            priority = 15
        
        # Specifically prioritize Gemini if we are inserting it
        if api_key == 'google_gemini':
            priority = 5 # Set a very high priority to make it the first choice
        
        # Insert into api_registry
        try:
            api_id = await conn.fetchval('''
                INSERT INTO api_registry (
                    api_key, name, description, provider, category,
                    base_url, documentation_url, auth_type, requires_auth,
                    rate_limit_per_second, rate_limit_per_minute, 
                    rate_limit_per_hour, rate_limit_per_day,
                    cost_type, free_tier_limit, priority,
                    supported_languages, is_active, is_healthy
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
                ON CONFLICT (api_key) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    base_url = EXCLUDED.base_url,
                    updated_at = NOW()
                RETURNING id
            ''', api_key, name, description, self._extract_provider(name), category,
                 base_url, documentation, auth_type, requires_auth,
                 rate_limits.get('per_second'), rate_limits.get('per_minute'),
                 rate_limits.get('per_hour'), rate_limits.get('per_day'),
                 cost_type, api_info.get('free_tier_limit', ''), priority,
                 languages, True, True)
            
            logger.info(f"Inserted/Updated API: {api_key} ({name})")
            
            # Insert endpoints if defined
            if 'endpoints' in api_info:
                await self._insert_endpoints(conn, api_id, api_info['endpoints'])
            
        except Exception as e:
            logger.error(f"Error inserting API {api_key}: {str(e)}")
    
    def _parse_rate_limits(self, rate_limit_text: str) -> Dict[str, Optional[int]]:
        """Extract rate limits from text like '100 requests/minute'."""
        limits = {
            'per_second': None,
            'per_minute': None,
            'per_hour': None,
            'per_day': None
        }
        
        if not rate_limit_text or 'unlimited' in rate_limit_text.lower():
            return limits
        
        import re
        
        # Look for patterns like "100 requests/minute" or "10/sec"
        patterns = [
            (r'(\d+)\s*(?:requests?)?[/\s]+(?:per\s+)?(?:second|sec)', 'per_second'),
            (r'(\d+)\s*(?:requests?)?[/\s]+(?:per\s+)?(?:minute|min)', 'per_minute'),
            (r'(\d+)\s*(?:requests?)?[/\s]+(?:per\s+)?(?:hour|hr)', 'per_hour'),
            (r'(\d+)\s*(?:requests?)?[/\s]+(?:per\s+)?day', 'per_day'),
        ]
        
        for pattern, key in patterns:
            match = re.search(pattern, rate_limit_text, re.IGNORECASE)
            if match:
                limits[key] = int(match.group(1))
        
        return limits
    
    def _extract_provider(self, name: str) -> str:
        """Extract provider name from API name."""
        providers = {
            'Google': ['Google', 'Gemini'],
            'Microsoft': ['Microsoft', 'Azure', 'Edge'],
            'Meta': ['Meta', 'Facebook'],
            'Groq': ['Groq'],
            'OpenAI': ['OpenAI', 'Whisper'],
            'Hugging Face': ['Hugging Face', 'HuggingFace'],
            'NIH': ['NIH', 'NLM', 'PubMed'],
            'FDA': ['FDA', 'openFDA'],
            'WHO': ['WHO']
        }
        
        for provider, keywords in providers.items():
            if any(keyword.lower() in name.lower() for keyword in keywords):
                return provider
        
        return 'Unknown'
    
    def _get_common_language_codes(self) -> List[str]:
        """Return common language codes for APIs that support '120+' languages."""
        return ['en', 'hi', 'te', 'ta', 'bn', 'mr', 'es', 'fr', 'de', 'it', 
                'pt', 'ru', 'ar', 'zh', 'ja', 'ko', 'vi', 'th', 'id', 'ms']
    
    async def _insert_endpoints(self, conn, api_id: str, endpoints: Dict):
        """Insert API endpoints."""
        for endpoint_name, endpoint_path in endpoints.items():
            try:
                await conn.execute('''
                    INSERT INTO api_endpoints (api_id, endpoint_name, endpoint_path)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (api_id, endpoint_name) DO NOTHING
                ''', api_id, endpoint_name, endpoint_path)
            except Exception as e:
                logger.error(f"Error inserting endpoint {endpoint_name}: {str(e)}")
    
    # =========================================================================
    # API CREDENTIAL MANAGEMENT
    # =========================================================================
    
    async def add_api_credential(self, api_key: str, credential_name: str, 
                                 credential_value: str, expires_at: Optional[datetime] = None):
        """
        Add an encrypted API credential to the database.
        
        Example:
            await manager.add_api_credential(
                'groq_whisper', 
                'api_key', 
                'gsk_xxxxxxxxxxxx'
            )
        """
        # Encrypt the credential
        encrypted_value = self.cipher.encrypt(credential_value.encode()).decode()
        
        async with self.pool.acquire() as conn:
            # Get API ID
            api_id = await conn.fetchval(
                'SELECT id FROM api_registry WHERE api_key = $1', api_key
            )
            
            if not api_id:
                raise ValueError(f"API '{api_key}' not found in database")
            
            # Insert credential
            await conn.execute('''
                INSERT INTO api_credentials (api_id, credential_name, credential_value, expires_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (api_id, credential_name) 
                DO UPDATE SET 
                    credential_value = EXCLUDED.credential_value,
                    expires_at = EXCLUDED.expires_at,
                    is_active = true
            ''', api_id, credential_name, encrypted_value, expires_at)
            
        logger.info(f"Added credential '{credential_name}' for API '{api_key}'")
    
    async def get_api_credential(self, api_key: str, credential_name: str = 'api_key') -> Optional[str]:
        """
        Retrieve and decrypt an API credential.
        
        Returns:
            Decrypted credential value or None if not found
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT ac.credential_value
                FROM api_credentials ac
                JOIN api_registry ar ON ac.api_id = ar.id
                WHERE ar.api_key = $1 
                  AND ac.credential_name = $2
                  AND ac.is_active = true
                  AND (ac.expires_at IS NULL OR ac.expires_at > NOW())
            ''', api_key, credential_name)
            
            if row:
                encrypted_value = row['credential_value']
                decrypted = self.cipher.decrypt(encrypted_value.encode()).decode()
                return decrypted
            
            return None
    
    # =========================================================================
    # INTELLIGENT API SELECTION
    # =========================================================================
    
    async def get_best_api(self, category: str, language: Optional[str] = None,
                          region: Optional[str] = None) -> Optional[Dict]:
        """
        Get the best available API for a specific purpose.
        
        This is the magic method that makes your system intelligent. It considers:
        - Is the API healthy? (no recent failures)
        - Is it rate-limited? (has quota remaining)
        - Is it in maintenance? (scheduled downtime)
        - What's its priority? (configured preference)
        - Does it support the requested language/region?
        
        Args:
            category: API category ('stt', 'tts', 'llm', etc.)
            language: Optional language code for filtering
            region: Optional region for compliance
        
        Returns:
            Dictionary with API details or None if no suitable API found
        
        Example:
            # Get best speech-to-text API for Hindi
            api = await manager.get_best_api('stt', language='hi')
            if api:
                result = await manager.call_api(api['api_key'], 'transcribe', audio_data)
        """
        # Check cache first
        cache_key = f"{category}:{language}:{region}"
        if cache_key in self._api_cache:
            cached_data, cached_time = self._api_cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data
        
        async with self.pool.acquire() as conn:
            # Use the database function we created
            row = await conn.fetchrow(
                'SELECT * FROM get_best_api($1, $2, $3)',
                category, language, region
            )
            
            if row:
                api_data = dict(row)
                
                # Get credential if needed
                credential = await self.get_api_credential(api_data['api_key'])
                if credential:
                    api_data['credential'] = credential
                
                # Cache the result
                self._api_cache[cache_key] = (api_data, time.time())
                
                logger.info(f"Selected API: {api_data['name']} for category '{category}'")
                return api_data
            
            logger.warning(f"No available API found for category '{category}'")
            return None
    
    async def get_fallback_api(self, primary_api_key: str) -> Optional[Dict]:
        """
        Get the fallback/backup API for a primary API.
        
        When the primary API fails, automatically switch to this one.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT ar2.*
                FROM api_registry ar1
                JOIN api_registry ar2 ON ar2.fallback_for = ar1.id
                WHERE ar1.api_key = $1
                  AND ar2.is_active = true
                  AND ar2.is_healthy = true
                ORDER BY ar2.priority ASC
                LIMIT 1
            ''', primary_api_key)
            
            if row:
                return dict(row)
            
            return None
    
    # =========================================================================
    # API CALLING WITH AUTOMATIC RETRY & FAILOVER
    # =========================================================================
    
    async def call_api(self, api_key: str, endpoint: str, data: Dict[str, Any],
                      session_id: Optional[str] = None, max_retries: int = 2) -> Tuple[bool, Any]:
        """
        Call an API with automatic error handling, rate limiting, and failover.
        
        This method handles all the complexity:
        1. Checks if we're rate-limited
        2. Makes the API call
        3. Records usage statistics
        4. On failure, automatically tries fallback APIs
        5. Updates health status
        
        Args:
            api_key: Which API to use
            endpoint: Endpoint name ('transcribe', 'synthesize', etc.)
            data: Request data/parameters
            session_id: Optional session ID for tracking
            max_retries: Number of retry attempts
        
        Returns:
            Tuple of (success: bool, response_data: Any)
        
        Example:
            success, result = await manager.call_api(
                'groq_whisper',
                'transcribe',
                {'audio': audio_bytes, 'model': 'whisper-large-v3'}
            )
            
            if success:
                print(f"Transcription: {result['text']}")
            else:
                print(f"Error: {result}")
        """
        start_time = time.time()
        
        # Get API details
        async with self.pool.acquire() as conn:
            api_info = await conn.fetchrow(
                'SELECT * FROM api_registry WHERE api_key = $1', api_key
            )
            
            if not api_info:
                return False, {'error': f"API '{api_key}' not found"}
            
            api_id = api_info['id']
            
            # Check rate limit
            can_proceed = await conn.fetchval(
                'SELECT increment_rate_limit($1, $2)',
                api_id, timedelta(minutes=1)
            )
            
            if not can_proceed:
                logger.warning(f"Rate limit exceeded for {api_key}")
                
                # Try fallback
                fallback = await self.get_fallback_api(api_key)
                if fallback:
                    logger.info(f"Switching to fallback: {fallback['name']}")
                    return await self.call_api(
                        fallback['api_key'], endpoint, data, session_id, max_retries
                    )
                
                return False, {'error': 'Rate limit exceeded and no fallback available'}
        
        # Get endpoint details
        async with self.pool.acquire() as conn:
            endpoint_info = await conn.fetchrow('''
                SELECT * FROM api_endpoints 
                WHERE api_id = $1 AND endpoint_name = $2
            ''', api_id, endpoint)
        
        # Build request URL
        base_url = api_info['base_url'].rstrip('/')
        endpoint_path = ""
        if endpoint_info:
            endpoint_path = endpoint_info['endpoint_path'].lstrip('/')
            http_method = endpoint_info['http_method']
        
        url = f"{base_url}/{endpoint_path}" if endpoint_path else base_url
        
        # Get credentials and set up auth
        credential = await self.get_api_credential(api_key)
        headers = {'Content-Type': 'application/json'}
        params = {} # For URL query parameters

        if credential:
            # Special handling for Gemini API which uses a key in the URL
            if api_key == 'google_gemini':
                params['key'] = credential
            elif api_info['auth_type'] == 'api_key' or api_info['auth_type'] == 'bearer':
                headers['Authorization'] = f"Bearer {credential}"

        # Make the API call
        try:
            if http_method == 'GET':
                # For GET, merge data into params
                params.update(data)
                async with self._http_session.get(url, params=params, headers=headers) as response:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    success = 200 <= response.status < 300
                    result = await response.json() if success else await response.text()
            else: # POST, PUT, etc.
                async with self._http_session.post(url, params=params, json=data, headers=headers) as response:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    success = 200 <= response.status < 300
                    result = await response.json() if success else await response.text()
            
            # Record usage
            await self._record_usage(
                api_id, endpoint, response_time_ms, success,
                response.status,
                result if not success else None,
                session_id
            )
            
            return success, result
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            
            logger.error(f"API call failed for {api_key}: {error_msg}")
            
            # Record failure
            await self._record_usage(
                api_id, endpoint, response_time_ms, False,
                500, error_msg, session_id
            )
            
            # Retry logic
            if max_retries > 0:
                logger.info(f"Retrying... ({max_retries} attempts left)")
                await asyncio.sleep(1)  # Brief delay before retry
                return await self.call_api(api_key, endpoint, data, session_id, max_retries - 1)
            
            # Try fallback
            fallback = await self.get_fallback_api(api_key)
            if fallback:
                logger.info(f"Primary failed, trying fallback: {fallback['name']}")
                return await self.call_api(
                    fallback['api_key'], endpoint, data, session_id, 0
                )
            
            return False, {'error': error_msg}
    
    async def _record_usage(self, api_id: str, endpoint: str, response_time_ms: int,
                           success: bool, status_code: int, error_msg: Optional[str],
                           session_id: Optional[str]):
        """Record API usage in the database."""
        async with self.pool.acquire() as conn:
            await conn.fetchval(
                'SELECT record_api_usage($1, $2, $3, $4, $5, $6, $7)',
                api_id, endpoint, response_time_ms, success,
                status_code, error_msg, session_id
            )
    
    # =========================================================================
    # HEALTH MONITORING
    # =========================================================================
    
    async def check_api_health(self, api_key: str) -> bool:
        """
        Perform a health check on an API by making a test call.
        
        Returns:
            True if healthy, False otherwise
        """
        async with self.pool.acquire() as conn:
            api_info = await conn.fetchrow(
                'SELECT * FROM api_registry WHERE api_key = $1', api_key
            )
            
            if not api_info:
                return False
            
            # Simple health check - try to connect
            try:
                start_time = time.time()
                async with self._http_session.get(api_info['base_url'], timeout=aiohttp.ClientTimeout(total=5)) as response:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    is_healthy = response.status < 500
                    
                    # Record health check
                    await conn.execute('''
                        INSERT INTO api_health_checks (api_id, is_healthy, response_time_ms, status_code)
                        VALUES ($1, $2, $3, $4)
                    ''', api_info['id'], is_healthy, response_time_ms, response.status)
                    
                    # Update API registry
                    await conn.execute('''
                        UPDATE api_registry
                        SET is_healthy = $1, last_health_check = NOW()
                        WHERE id = $2
                    ''', is_healthy, api_info['id'])
                    
                    return is_healthy
                    
            except Exception as e:
                logger.error(f"Health check failed for {api_key}: {str(e)}")
                
                # Mark as unhealthy
                await conn.execute('''
                    UPDATE api_registry
                    SET is_healthy = false, 
                        last_health_check = NOW(),
                        consecutive_failures = consecutive_failures + 1
                    WHERE id = $1
                ''', api_info['id'])
                
                return False
    
    async def check_all_apis_health(self):
        """Run health checks on all active APIs."""
        async with self.pool.acquire() as conn:
            api_keys = await conn.fetch(
                'SELECT api_key FROM api_registry WHERE is_active = true'
            )
            
            tasks = [self.check_api_health(row['api_key']) for row in api_keys]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            healthy_count = sum(1 for r in results if r is True)
            total_count = len(results)
            
            logger.info(f"Health check complete: {healthy_count}/{total_count} APIs healthy")
    
    # =========================================================================
    # ANALYTICS & REPORTING
    # =========================================================================
    
    async def get_usage_stats(self, hours: int = 24) -> List[Dict]:
        """
        Get usage statistics for the last N hours.
        
        Returns list of API usage summaries.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch('''
                SELECT 
                    ar.api_key,
                    ar.name,
                    ar.category,
                    COUNT(*) as total_requests,
                    COUNT(*) FILTER (WHERE aul.success = true) as successful_requests,
                    ROUND(AVG(aul.response_time_ms)::numeric, 2) as avg_response_time,
                    ROUND((COUNT(*) FILTER (WHERE aul.success = true)::numeric / 
                           NULLIF(COUNT(*), 0) * 100), 2) as success_rate
                FROM api_registry ar
                JOIN api_usage_log aul ON ar.id = aul.api_id
                WHERE aul.request_timestamp > NOW() - ($1 || ' hours')::INTERVAL
                GROUP BY ar.id, ar.api_key, ar.name, ar.category
                ORDER BY total_requests DESC
            ''', hours)
            
            return [dict(row) for row in rows]
    
    async def get_api_status_dashboard(self) -> Dict:
        """
        Get a dashboard summary of all APIs.
        
        Returns:
            Dictionary with overall system status
        """
        async with self.pool.acquire() as conn:
            total_apis = await conn.fetchval('SELECT COUNT(*) FROM api_registry WHERE is_active = true')
            healthy_apis = await conn.fetchval('SELECT COUNT(*) FROM api_registry WHERE is_active = true AND is_healthy = true')
            
            # Get top performing APIs
            top_apis = await conn.fetch('''
                SELECT api_key, name, quality_score, average_latency_ms
                FROM api_registry
                WHERE is_active = true
                ORDER BY quality_score DESC, average_latency_ms ASC
                LIMIT 5
            ''')
            
            return {
                'total_apis': total_apis,
                'healthy_apis': healthy_apis,
                'health_percentage': round((healthy_apis / total_apis * 100) if total_apis > 0 else 0, 2),
                'top_performers': [dict(row) for row in top_apis]
            }


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def main():
    """
    Example usage of the API Manager.
    
    This shows the complete workflow from initialization to making API calls.
    """
    
    # 1. Initialize the API Manager
    manager = APIManager(
        db_url="postgresql://user:password@localhost:5432/openvitality"
    )
    await manager.initialize()
    
    try:
        # 2. Populate database from YAML (run once during setup)
        # await manager.populate_from_yaml('apis_database.yaml')
        
        # 3. Add API credentials (your actual API keys)
        await manager.add_api_credential('google_gemini', 'api_key', 'YOUR_GEMINI_API_KEY')
        await manager.add_api_credential('groq_whisper', 'api_key', 'YOUR_GROQ_API_KEY')
        
        # 4. Get the best API for speech-to-text (Hindi language)
        stt_api = await manager.get_best_api('stt', language='hi')
        if stt_api:
            print(f"Selected STT API: {stt_api['name']}")
            
            # 5. Make an API call (example)
            # success, result = await manager.call_api(
            #     stt_api['api_key'],
            #     'transcribe',
            #     {'audio': audio_bytes, 'language': 'hi'}
            # )
            # if success:
            #     print(f"Transcription: {result['text']}")
        
        # 6. Get usage statistics
        stats = await manager.get_usage_stats(hours=24)
        print("\nUsage Statistics (Last 24 hours):")
        for stat in stats:
            print(f"  {stat['name']}: {stat['total_requests']} requests, "
                  f"{stat['success_rate']}% success rate")
        
        # 7. Get system dashboard
        dashboard = await manager.get_api_status_dashboard()
        print(f"\nSystem Status: {dashboard['healthy_apis']}/{dashboard['total_apis']} APIs healthy")
        
    finally:
        # Always clean up
        await manager.close()


if __name__ == '__main__':
    asyncio.run(main())
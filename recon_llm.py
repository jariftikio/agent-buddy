import aiohttp
import asyncio
import json
import logging
from typing import Dict, Any, List
from openai import AsyncOpenAI # Assuming Llama 3.2 is accessible via an OpenAI-compatible endpoint

logger = logging.getLogger(__name__)

class HermesLLMRecon:
    def __init__(self, serper_api_key: str, llm_endpoint: str, llm_api_key: str):
        self.serper_api_key = serper_api_key
        self.llm_client = AsyncOpenAI(base_url=llm_endpoint, api_key=llm_api_key)
        self.llm_model = "llama-3.2-7b" # Or your specific model identifier

    async def search_serper(self, query: str) -> List[Dict]:
        """Search Google via Serper."""
        url = "https://google.serper.dev/search"
        headers = {
            'X-API-KEY': self.serper_api_key,
            'Content-Type': 'application/json'
        }
        payload = {'q': query}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('organic', []) + data.get('knowledgeGraph', {})
        except Exception as e:
            logger.error(f"Serper search failed for '{query}': {e}")
        return []

    async def extract_pii_from_results(self, search_results: List[Any], target_name: str) -> Dict[str, Any]:
        """Use Llama 3.2 to extract PII from search results."""
        prompt = f"""
        Analyze the following search results for information about "{target_name}".
        Extract any available Name, Email Address, and Phone Number.
        Return ONLY a valid JSON object with keys: "emails", "phones", "names".
        If no info is found for a key, use an empty list.
        
        Search Results:
        {json.dumps(search_results)}
        """
        
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2 # Low temp for factual extraction
            )
            content = response.choices[0].message.content
            # Clean markdown code block if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {"emails": [], "phones": [], "names": []}

    async def recon_by_name(self, name: str) -> Dict[str, Any]:
        """Full recon loop for a name."""
        queries = [
            f"{name} email contact",
            f"{name} phone number",
            f"{name} linkedin profile",
            f"{name} company website"
        ]
        
        all_results = []
        for q in queries:
            results = await self.search_serper(q)
            all_results.extend(results)
            
        pii_data = await self.extract_pii_from_results(all_results, name)
        
        return {
            "target": name,
            "pii": pii_data,
            "sources_count": len(all_results)
        }

# Example Usage
async def main():
    # Replace with actual endpoints/keys
    recon = HermesLLMRecon(
        serper_api_key="YOUR_SERPER_KEY",
        llm_endpoint="http://localhost:8000/v1", # Local Llama instance or cloud provider
        llm_api_key="dummy" 
    )
    
    result = await recon.recon_by_name("John Doe")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())

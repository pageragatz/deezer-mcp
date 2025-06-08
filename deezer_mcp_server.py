"""
Serveur MCP pour l'API Deezer
Permet la recherche, la récupération et la gestion de contenu musical via l'API Deezer Simple.
"""

import logging
from typing import Dict, Any, Optional
import aiohttp
from fastmcp import FastMCP
from pydantic import BaseModel, Field, validator
import json

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation du serveur MCP
mcp = FastMCP("Deezer Music Server")

# Configuration de base
BASE_URL = "https://api.deezer.com"
DEFAULT_LIMIT = 3  # Limite maximale de 3 résultats par défaut

class DeezerAPIError(Exception):
    """Exception personnalisée pour les erreurs de l'API Deezer"""
    pass

class SearchParams(BaseModel):
    """Paramètres pour la recherche musicale"""
    query: str = Field(..., description="Terme de recherche")
    limit: int = Field(default=3, ge=1, le=3, description="Nombre de résultats à retourner (max 3)")
    strict: bool = Field(default=False, description="Désactiver le mode fuzzy")
    order: str = Field(default="RANKING", description="Ordre de tri des résultats")
    
    @validator('order')
    def validate_order(cls, v):
        valid_orders = [
            "RANKING", "TRACK_ASC", "TRACK_DESC", "ARTIST_ASC", "ARTIST_DESC",
            "ALBUM_ASC", "ALBUM_DESC", "RATING_ASC", "RATING_DESC", 
            "DURATION_ASC", "DURATION_DESC"
        ]
        if v not in valid_orders:
            raise ValueError(f"Order must be one of {valid_orders}")
        return v

class AdvancedSearchParams(BaseModel):
    """Paramètres pour la recherche avancée"""
    artist: Optional[str] = Field(None, description="Nom de l'artiste")
    album: Optional[str] = Field(None, description="Titre de l'album")
    track: Optional[str] = Field(None, description="Titre de la piste")
    label: Optional[str] = Field(None, description="Nom du label")
    dur_min: Optional[int] = Field(None, ge=0, description="Durée minimale en secondes")
    dur_max: Optional[int] = Field(None, ge=0, description="Durée maximale en secondes")
    bpm_min: Optional[int] = Field(None, ge=0, description="BPM minimum")
    bpm_max: Optional[int] = Field(None, ge=0, description="BPM maximum")
    limit: int = Field(default=3, ge=1, le=3, description="Nombre de résultats (max 3)")
    strict: bool = Field(default=False, description="Mode strict")
    order: str = Field(default="RANKING", description="Ordre de tri")

async def make_api_request(session: aiohttp.ClientSession, endpoint: str, params: Dict = None) -> Dict[str, Any]:
    """Effectue une requête à l'API Deezer avec gestion d'erreurs"""
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    
    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if "error" in data:
                    raise DeezerAPIError(f"API Error: {data['error']}")
                return data
            else:
                raise DeezerAPIError(f"HTTP {response.status}: {await response.text()}")
    except aiohttp.ClientError as e:
        raise DeezerAPIError(f"Request failed: {str(e)}")

@mcp.tool()
async def search_tracks(params: SearchParams) -> Dict[str, Any]:
    """
    Recherche des pistes musicales sur Deezer
    
    Args:
        params: Paramètres de recherche incluant la requête, limite et options de tri
        
    Returns:
        Dict contenant les résultats de recherche avec métadonnées
        
    Example:
        search_tracks({"query": "eminem lose yourself", "limit": 3})
    """
    search_params = {
        "q": params.query,
        "limit": min(params.limit, 3)  # Force la limite à 3 maximum
    }
    
    if params.strict:
        search_params["strict"] = "on"
    if params.order != "RANKING":
        search_params["order"] = params.order
    
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, "search", search_params)
            return {
                "success": True,
                "query": params.query,
                "total": result.get("total", 0),
                "tracks": result.get("data", [])[:3],  # Limite les résultats à 3
                "next": result.get("next"),
                "prev": result.get("prev")
            }
        except DeezerAPIError as e:
            logger.error(f"Search error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def advanced_search(params: AdvancedSearchParams) -> Dict[str, Any]:
    """
    Effectue une recherche avancée avec des critères spécifiques
    
    Args:
        params: Paramètres de recherche avancée
        
    Returns:
        Dict contenant les résultats de recherche filtrés
        
    Example:
        advanced_search({"artist": "daft punk", "bpm_min": 120, "dur_min": 180})
    """
    # Construction de la requête avancée
    query_parts = []
    
    if params.artist:
        query_parts.append(f'artist:"{params.artist}"')
    if params.album:
        query_parts.append(f'album:"{params.album}"')
    if params.track:
        query_parts.append(f'track:"{params.track}"')
    if params.label:
        query_parts.append(f'label:"{params.label}"')
    if params.dur_min:
        query_parts.append(f'dur_min:{params.dur_min}')
    if params.dur_max:
        query_parts.append(f'dur_max:{params.dur_max}')
    if params.bpm_min:
        query_parts.append(f'bpm_min:{params.bpm_min}')
    if params.bpm_max:
        query_parts.append(f'bpm_max:{params.bpm_max}')
    
    if not query_parts:
        return {"success": False, "error": "Au moins un critère de recherche est requis"}
    
    query = " ".join(query_parts)
    
    search_params = {
        "q": query,
        "limit": min(params.limit, 3)  # Force la limite à 3 maximum
    }
    
    if params.strict:
        search_params["strict"] = "on"
    if params.order != "RANKING":
        search_params["order"] = params.order
    
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, "search", search_params)
            return {
                "success": True,
                "query": query,
                "criteria": {k: v for k, v in params.dict().items() if v is not None and k not in ['limit', 'strict', 'order']},
                "total": result.get("total", 0),
                "tracks": result.get("data", [])[:3],  # Limite les résultats à 3
                "next": result.get("next"),
                "prev": result.get("prev")
            }
        except DeezerAPIError as e:
            logger.error(f"Advanced search error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def get_track_details(track_id: int) -> Dict[str, Any]:
    """
    Récupère les détails complets d'une piste musicale
    
    Args:
        track_id: ID Deezer de la piste
        
    Returns:
        Dict contenant toutes les informations de la piste
        
    Example:
        get_track_details(3135556)
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, f"track/{track_id}")
            return {
                "success": True,
                "track": result
            }
        except DeezerAPIError as e:
            logger.error(f"Track details error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def get_artist_details(artist_id: int) -> Dict[str, Any]:
    """
    Récupère les détails d'un artiste
    
    Args:
        artist_id: ID Deezer de l'artiste
        
    Returns:
        Dict contenant les informations de l'artiste
        
    Example:
        get_artist_details(27)
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, f"artist/{artist_id}")
            return {
                "success": True,
                "artist": result
            }
        except DeezerAPIError as e:
            logger.error(f"Artist details error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def get_artist_albums(artist_id: int, limit: int = Field(default=50, ge=1, le=100)) -> Dict[str, Any]:
    """
    Récupère les albums d'un artiste
    
    Args:
        artist_id: ID Deezer de l'artiste
        limit: Nombre d'albums à récupérer
        
    Returns:
        Dict contenant la liste des albums
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, f"artist/{artist_id}/albums", {"limit": limit})
            return {
                "success": True,
                "artist_id": artist_id,
                "total": result.get("total", 0),
                "albums": result.get("data", [])
            }
        except DeezerAPIError as e:
            logger.error(f"Artist albums error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def get_artist_top_tracks(artist_id: int, limit: int = Field(default=50, ge=1, le=100)) -> Dict[str, Any]:
    """
    Récupère les meilleures pistes d'un artiste
    
    Args:
        artist_id: ID Deezer de l'artiste
        limit: Nombre de pistes à récupérer
        
    Returns:
        Dict contenant les meilleures pistes
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, f"artist/{artist_id}/top", {"limit": limit})
            return {
                "success": True,
                "artist_id": artist_id,
                "total": result.get("total", 0),
                "top_tracks": result.get("data", [])
            }
        except DeezerAPIError as e:
            logger.error(f"Artist top tracks error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def get_album_details(album_id: int) -> Dict[str, Any]:
    """
    Récupère les détails d'un album
    
    Args:
        album_id: ID Deezer de l'album
        
    Returns:
        Dict contenant les informations de l'album
        
    Example:
        get_album_details(302127)
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, f"album/{album_id}")
            return {
                "success": True,
                "album": result
            }
        except DeezerAPIError as e:
            logger.error(f"Album details error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def get_playlist_details(playlist_id: int) -> Dict[str, Any]:
    """
    Récupère les détails d'une playlist
    
    Args:
        playlist_id: ID Deezer de la playlist
        
    Returns:
        Dict contenant les informations de la playlist
        
    Example:
        get_playlist_details(908622995)
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, f"playlist/{playlist_id}")
            return {
                "success": True,
                "playlist": result
            }
        except DeezerAPIError as e:
            logger.error(f"Playlist details error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def search_artists(query: str, limit: int = Field(default=3, ge=1, le=3)) -> Dict[str, Any]:
    """
    Recherche d'artistes sur Deezer
    
    Args:
        query: Terme de recherche pour les artistes
        limit: Nombre de résultats à retourner (max 3)
        
    Returns:
        Dict contenant les artistes trouvés
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, "search/artist", {"q": query, "limit": min(limit, 3)})
            return {
                "success": True,
                "query": query,
                "total": result.get("total", 0),
                "artists": result.get("data", [])[:3]  # Limite les résultats à 3
            }
        except DeezerAPIError as e:
            logger.error(f"Artist search error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def search_albums(query: str, limit: int = Field(default=3, ge=1, le=3)) -> Dict[str, Any]:
    """
    Recherche d'albums sur Deezer
    
    Args:
        query: Terme de recherche pour les albums
        limit: Nombre de résultats à retourner (max 3)
        
    Returns:
        Dict contenant les albums trouvés
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, "search/album", {"q": query, "limit": min(limit, 3)})
            return {
                "success": True,
                "query": query,
                "total": result.get("total", 0),
                "albums": result.get("data", [])[:3]  # Limite les résultats à 3
            }
        except DeezerAPIError as e:
            logger.error(f"Album search error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def search_playlists(query: str, limit: int = Field(default=3, ge=1, le=3)) -> Dict[str, Any]:
    """
    Recherche de playlists sur Deezer
    
    Args:
        query: Terme de recherche pour les playlists
        limit: Nombre de résultats à retourner (max 3)
        
    Returns:
        Dict contenant les playlists trouvées
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, "search/playlist", {"q": query, "limit": min(limit, 3)})
            return {
                "success": True,
                "query": query,
                "total": result.get("total", 0),
                "playlists": result.get("data", [])[:3]  # Limite les résultats à 3
            }
        except DeezerAPIError as e:
            logger.error(f"Playlist search error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def get_genre_list() -> Dict[str, Any]:
    """
    Récupère la liste des genres musicaux disponibles sur Deezer
    
    Returns:
        Dict contenant tous les genres disponibles
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, "genre")
            return {
                "success": True,
                "genres": result.get("data", [])
            }
        except DeezerAPIError as e:
            logger.error(f"Genres error: {e}")
            return {"success": False, "error": str(e)}

@mcp.tool()
async def get_genre_artists(genre_id: int, limit: int = Field(default=25, ge=1, le=100)) -> Dict[str, Any]:
    """
    Récupère les artistes d'un genre spécifique
    
    Args:
        genre_id: ID du genre musical
        limit: Nombre d'artistes à récupérer
        
    Returns:
        Dict contenant les artistes du genre
    """
    async with aiohttp.ClientSession() as session:
        try:
            result = await make_api_request(session, f"genre/{genre_id}/artists", {"limit": limit})
            return {
                "success": True,
                "genre_id": genre_id,
                "total": result.get("total", 0),
                "artists": result.get("data", [])
            }
        except DeezerAPIError as e:
            logger.error(f"Genre artists error: {e}")
            return {"success": False, "error": str(e)}

# Resources pour exposer des données statiques
@mcp.resource("deezer://api-endpoints")
async def get_api_endpoints() -> str:
    """Documentation des endpoints disponibles de l'API Deezer"""
    endpoints = {
        "search": {
            "tracks": "/search?q={query}",
            "artists": "/search/artist?q={query}",
            "albums": "/search/album?q={query}",
            "playlists": "/search/playlist?q={query}"
        },
        "details": {
            "track": "/track/{id}",
            "artist": "/artist/{id}",
            "album": "/album/{id}",
            "playlist": "/playlist/{id}"
        },
        "artist_content": {
            "albums": "/artist/{id}/albums",
            "top_tracks": "/artist/{id}/top"
        },
        "genres": "/genre"
    }
    return json.dumps(endpoints, indent=2)

@mcp.resource("deezer://search-examples")
async def get_search_examples() -> str:
    """Exemples de recherches avancées"""
    examples = {
        "basic_search": {
            "description": "Recherche simple",
            "example": 'search_tracks({"query": "daft punk", "limit": 2})'
        },
        "advanced_search": {
            "description": "Recherche avec critères spécifiques",
            "examples": [
                'advanced_search({"artist": "daft punk", "bpm_min": 120})',
                'advanced_search({"album": "random access memories", "dur_min": 300})',
                'advanced_search({"track": "get lucky", "label": "columbia"})'
            ]
        },
        "search_modifiers": {
            "artist": 'artist:"nom de l\'artiste"',
            "album": 'album:"titre de l\'album"',
            "track": 'track:"titre de la piste"',
            "label": 'label:"nom du label"',
            "duration": 'dur_min:300 dur_max:500',
            "bpm": 'bpm_min:120 bpm_max:140'
        }
    }
    return json.dumps(examples, indent=2)

# Prompt système pour l'assistance
@mcp.prompt("deezer-search-assistant")
async def deezer_search_assistant() -> str:
    """Assistant pour optimiser les recherches musicales sur Deezer"""
    return """
Tu es un assistant spécialisé dans la recherche musicale via l'API Deezer.
Tu peux aider les utilisateurs à :

1. **Recherches basiques** :
   - Rechercher des pistes, artistes, albums, playlists
   - Utiliser des filtres de tri et de limite (max 3 résultats)
   - Note importante : Toutes les recherches sont limitées à 3 résultats maximum

2. **Recherches avancées** :
   - Combiner plusieurs critères (artiste + durée + BPM)
   - Utiliser des filtres précis pour affiner les résultats
   - Limiter les résultats à 3 maximum pour des réponses rapides

3. **Exploration de contenu** :
   - Découvrir les albums d'un artiste
   - Trouver les meilleures pistes d'un artiste
   - Explorer les genres musicaux
   - Toujours limiter les résultats à 3 pour une meilleure performance

4. **Conseils d'optimisation** :
   - Utiliser le mode strict pour des résultats exacts
   - Choisir le bon ordre de tri selon les besoins
   - Limiter les résultats à 3 pour des recherches rapides et efficaces

Exemples de recherches efficaces :
- Pour trouver une chanson précise : utilise artist:"nom" track:"titre"
- Pour découvrir de la musique danceable : bpm_min:120 bpm_max:140
- Pour des morceaux longs : dur_min:300
- Pour explorer un genre : utilise get_genre_list puis get_genre_artists

Toujours suggérer des modifications de recherche si les résultats ne semblent pas correspondre aux attentes.
Rappeler que les résultats sont limités à 3 maximum pour optimiser les performances.
"""

if __name__ == "__main__":
    transport = "sse"
    # Configuration pour le serveur MCP
    if transport == "stdio":
        mcp.run()
    elif transport == "sse":
        mcp.run(host="0.0.0.0", port=8000, transport="sse")
    else:
        raise ValueError(f"Transport non supporté: {transport}")


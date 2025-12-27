"""Identity resolution service for unifying entities across data sources."""
import re
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from core.models import NormalizedData

logger = logging.getLogger(__name__)


class IdentityResolver:
    """
    Resolves canonical identities for entities across multiple data sources.
    
    Uses various matching strategies to identify when records from different
    sources refer to the same real-world entity (e.g., the same cryptocurrency,
    news article, or data point).
    """
    
    def __init__(self, db: Session):
        self.db = db
        
        # Cryptocurrency symbol mappings (extensible)
        self.crypto_symbols = {
            'btc': 'bitcoin',
            'eth': 'ethereum',
            'usdt': 'tether',
            'bnb': 'binance-coin',
            'sol': 'solana',
            'xrp': 'ripple',
            'usdc': 'usd-coin',
            'ada': 'cardano',
            'avax': 'avalanche',
            'doge': 'dogecoin',
            'dot': 'polkadot',
            'matic': 'polygon',
            'shib': 'shiba-inu',
            'dai': 'dai',
            'trx': 'tron',
            'link': 'chainlink',
            'uni': 'uniswap',
            'atom': 'cosmos',
            'ltc': 'litecoin',
            'xlm': 'stellar',
            'etc': 'ethereum-classic',
            'bch': 'bitcoin-cash',
            'near': 'near-protocol',
            'algo': 'algorand',
            'vet': 'vechain',
            'icp': 'internet-computer',
            'hbar': 'hedera',
            'apt': 'aptos',
            'arb': 'arbitrum',
            'op': 'optimism',
            'fil': 'filecoin',
            'imx': 'immutable-x',
            'ldo': 'lido-dao',
            'crv': 'curve',
            'grt': 'the-graph',
            'aave': 'aave',
            'mkr': 'maker',
            'snx': 'synthetix',
            'rune': 'thorchain',
            'inj': 'injective',
            'ftm': 'fantom',
            'tia': 'celestia',
        }
        
        # Reverse mapping for quick lookup
        self.name_to_canonical = {}
        for symbol, name in self.crypto_symbols.items():
            self.name_to_canonical[symbol] = name
            self.name_to_canonical[name] = name
            self.name_to_canonical[name.replace('-', ' ')] = name
            self.name_to_canonical[name.replace('-', '')] = name
    
    def resolve_canonical_id(
        self,
        source_type: str,
        title: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Resolve the canonical identity for an entity.
        
        Args:
            source_type: Type of data source (csv, api_*, rss)
            title: Entity title/name
            data: Additional data fields for matching
            
        Returns:
            Canonical ID string
        """
        # Strategy 1: Extract from CSV-style IDs (e.g., "btc-bitcoin", "eth-ethereum")
        if source_type == "csv" and 'id' in data:
            csv_id = data['id']
            # Check if it's already in canonical format (symbol-name)
            if '-' in csv_id:
                parts = csv_id.split('-', 1)
                symbol = parts[0].lower()
                if symbol in self.crypto_symbols:
                    return self.crypto_symbols[symbol]
                return csv_id  # Use as-is if not recognized
        
        # Strategy 2: Match cryptocurrency names/symbols
        canonical = self._match_cryptocurrency(title, data)
        if canonical:
            return canonical
        
        # Strategy 3: URL-based matching for RSS feeds
        if source_type == "rss" and 'link' in data:
            url_canonical = self._extract_from_url(data['link'])
            if url_canonical:
                return url_canonical
        
        # Strategy 4: Normalize title as fallback
        # Create a normalized canonical ID from the title
        normalized_title = self._normalize_title(title)
        return normalized_title
    
    def _match_cryptocurrency(
        self,
        title: str,
        data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Match cryptocurrency by various fields.
        
        Args:
            title: Entity title
            data: Additional fields (symbol, name, ticker, etc.)
            
        Returns:
            Canonical crypto ID or None
        """
        # Check common crypto fields
        for field in ['symbol', 'ticker', 'coin_symbol', 'currency']:
            if field in data and data[field]:
                symbol = str(data[field]).lower().strip()
                if symbol in self.name_to_canonical:
                    return self.name_to_canonical[symbol]
        
        # Check title/name matching
        title_lower = title.lower().strip()
        
        # Direct match
        if title_lower in self.name_to_canonical:
            return self.name_to_canonical[title_lower]
        
        # Extract symbol from title (e.g., "Bitcoin (BTC)" -> "btc")
        symbol_match = re.search(r'\(([A-Z]{2,6})\)', title)
        if symbol_match:
            symbol = symbol_match.group(1).lower()
            if symbol in self.name_to_canonical:
                return self.name_to_canonical[symbol]
        
        # Check if title contains a known crypto name
        for known_name, canonical in self.name_to_canonical.items():
            if known_name in title_lower or title_lower in known_name:
                return canonical
        
        return None
    
    def _extract_from_url(self, url: str) -> Optional[str]:
        """
        Extract canonical ID from URL patterns.
        
        Args:
            url: URL string
            
        Returns:
            Canonical ID or None
        """
        # Pattern: /coins/{symbol}/ or /coin/{symbol}/
        coin_match = re.search(r'/coins?/([a-z0-9-]+)', url.lower())
        if coin_match:
            symbol = coin_match.group(1)
            if symbol in self.name_to_canonical:
                return self.name_to_canonical[symbol]
            return symbol
        
        return None
    
    def _normalize_title(self, title: str) -> str:
        """
        Normalize title to create a canonical ID.
        
        Args:
            title: Original title
            
        Returns:
            Normalized canonical ID
        """
        # Convert to lowercase
        normalized = title.lower().strip()
        
        # Remove special characters, keep alphanumeric and hyphens
        normalized = re.sub(r'[^\w\s-]', '', normalized)
        
        # Replace spaces with hyphens
        normalized = re.sub(r'\s+', '-', normalized)
        
        # Remove multiple consecutive hyphens
        normalized = re.sub(r'-+', '-', normalized)
        
        # Trim hyphens from ends
        normalized = normalized.strip('-')
        
        # Limit length
        if len(normalized) > 100:
            normalized = normalized[:100]
        
        return normalized or 'unknown'
    
    def find_matching_record(
        self,
        canonical_id: str,
        source_type: str
    ) -> Optional[NormalizedData]:
        """
        Find existing record with the same canonical ID from a different source.
        
        Args:
            canonical_id: Canonical identity to search for
            source_type: Current source type (to exclude from search)
            
        Returns:
            Existing NormalizedData record or None
        """
        return self.db.query(NormalizedData).filter(
            NormalizedData.canonical_id == canonical_id,
            NormalizedData.source_type != source_type
        ).first()
    
    def get_all_sources_for_entity(
        self,
        canonical_id: str
    ) -> List[NormalizedData]:
        """
        Get all source records for a canonical entity.
        
        Args:
            canonical_id: Canonical identity
            
        Returns:
            List of all records with this canonical ID
        """
        return self.db.query(NormalizedData).filter(
            NormalizedData.canonical_id == canonical_id
        ).order_by(NormalizedData.created_at).all()

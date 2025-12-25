# Cryptocurrency ETL Backend - API Configuration Guide

## Overview

This ETL system ingests cryptocurrency data from multiple sources:

1. **CoinPaprika API** - Primary cryptocurrency ticker data
2. **CoinGecko API** - Secondary cryptocurrency market data
3. **CSV Files** - Historical cryptocurrency data
4. **RSS Feed** - Cryptocurrency news from Cointelegraph

## API 1: CoinPaprika

### Getting Started

1. **Create Account**: Visit https://coinpaprika.com/api
2. **Get API Key**: Sign up for a free tier account
3. **API Limits**: Free tier includes:
   - 25,000 calls/month
   - No credit card required
   - Rate limit: ~17 calls/minute

### Configuration

```bash
# In your .env file
API_KEY_SOURCE_1=your_coinpaprika_api_key_here
API_URL_SOURCE_1=https://api.coinpaprika.com/v1/tickers
```

### API Response Format

CoinPaprika returns an array of tickers:

```json
[
  {
    "id": "btc-bitcoin",
    "name": "Bitcoin",
    "symbol": "BTC",
    "rank": 1,
    "circulating_supply": 19000000,
    "total_supply": 21000000,
    "max_supply": 21000000,
    "beta_value": 1.0,
    "quotes": {
      "USD": {
        "price": 45000.50,
        "volume_24h": 28000000000,
        "market_cap": 850000000000,
        "percent_change_1h": 0.5,
        "percent_change_24h": 2.3,
        "percent_change_7d": 5.1
      }
    }
  }
]
```

### Fields Mapped to Normalized Schema

- `id` → `source_id`
- `name` → `title`
- `symbol` + description → `description`
- `quotes.USD.price` → `value`
- `rank` or symbol type → `category`
- Current timestamp → `source_timestamp`
- Additional data → `metadata`

## API 2: CoinGecko

### Getting Started

1. **Free API**: No account required for basic usage
2. **Rate Limits**: 
   - 10-50 calls/minute (varies)
   - 50 results per page max
3. **Optional API Key**: For higher limits, visit https://www.coingecko.com/en/api/pricing

### Configuration

```bash
# In your .env file
API_KEY_SOURCE_2=  # Optional, leave empty for free tier
API_URL_SOURCE_2=https://api.coingecko.com/api/v3/coins/markets
```

### API Parameters

The ETL system calls CoinGecko with these parameters:

```
GET /api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1
```

### API Response Format

CoinGecko returns an array of market data:

```json
[
  {
    "id": "bitcoin",
    "symbol": "btc",
    "name": "Bitcoin",
    "current_price": 45000.50,
    "market_cap": 850000000000,
    "market_cap_rank": 1,
    "total_volume": 28000000000,
    "high_24h": 46000,
    "low_24h": 44000,
    "price_change_24h": 1000.50,
    "price_change_percentage_24h": 2.3,
    "circulating_supply": 19000000,
    "total_supply": 21000000,
    "ath": 69000,
    "ath_date": "2021-11-10T14:24:11.849Z",
    "last_updated": "2024-01-15T10:30:00.000Z"
  }
]
```

### Fields Mapped to Normalized Schema

- `id` → `source_id`
- `name` → `title`
- `symbol` + market data → `description`
- `current_price` → `value`
- `market_cap_rank` → `category` (e.g., "top-10", "top-100")
- `last_updated` → `source_timestamp`
- Additional data → `metadata`

## CSV Source

### Format

The CSV file should contain cryptocurrency data with these columns:

```csv
id,title,description,value,category,timestamp
btc-bitcoin,Bitcoin,Leading cryptocurrency,45000.50,cryptocurrency,2024-01-15T10:30:00Z
eth-ethereum,Ethereum,Smart contract platform,2500.75,cryptocurrency,2024-01-16T14:20:00Z
```

### Required Columns

- `id`: Unique identifier (e.g., "btc-bitcoin")
- `title`: Cryptocurrency name
- `description`: Brief description
- `value`: Current price in USD
- `category`: Type (cryptocurrency, stablecoin, etc.)
- `timestamp`: ISO 8601 format timestamp

## RSS Feed

### Source

Cointelegraph RSS feed for cryptocurrency news:

```bash
RSS_FEED_URL=https://cointelegraph.com/rss
```

### Data Extracted

- Title: Article headline
- Description: Article summary
- Link: URL to full article
- Published date: Publication timestamp
- Categories: Article tags/categories

## Authentication Configuration

### Environment Variables

Create a `.env` file with:

```bash
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/etl_db

# CoinPaprika API (Required)
API_KEY_SOURCE_1=your_coinpaprika_api_key_here
API_URL_SOURCE_1=https://api.coinpaprika.com/v1/tickers

# CoinGecko API (Optional - works without key)
API_KEY_SOURCE_2=
API_URL_SOURCE_2=https://api.coingecko.com/api/v3/coins/markets

# RSS Feed
RSS_FEED_URL=https://cointelegraph.com/rss

# CSV Path
CSV_SOURCE_PATH=./data/sample_data.csv
```

## Rate Limiting

The ETL system implements rate limiting to respect API limits:

- **Default**: 100 calls per 60 seconds
- **Configurable**: Set in `.env`:

```bash
ETL_RATE_LIMIT_CALLS=100
ETL_RATE_LIMIT_PERIOD=60
```

### Recommendations

- **CoinPaprika**: Use default settings (100/60s is well within limits)
- **CoinGecko**: May need to reduce to 50/60s for free tier

## Testing API Configuration

### 1. Test CoinPaprika API

```bash
curl -H "Authorization: your_api_key_here" \
  https://api.coinpaprika.com/v1/tickers?limit=5
```

Expected: JSON array of 5 cryptocurrency tickers

### 2. Test CoinGecko API

```bash
curl "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&per_page=5"
```

Expected: JSON array of 5 market data entries

### 3. Test RSS Feed

```bash
curl https://cointelegraph.com/rss
```

Expected: XML/RSS feed with news articles

## Troubleshooting

### CoinPaprika API Issues

**Problem**: "Invalid API key" error

**Solution**: 
- Verify API key is correct in `.env`
- Check for trailing spaces
- Ensure account is active

**Problem**: Rate limit exceeded

**Solution**:
- Reduce `ETL_RATE_LIMIT_CALLS`
- Increase `ETL_RATE_LIMIT_PERIOD`
- Check monthly quota usage

### CoinGecko API Issues

**Problem**: 429 Too Many Requests

**Solution**:
- Reduce request frequency
- Add delays between requests
- Consider getting an API key for higher limits

**Problem**: Empty response

**Solution**:
- Check URL parameters
- Verify `vs_currency=usd` is set
- Check API status: https://status.coingecko.com/

## Data Flow

```
CoinPaprika API → Validate → raw_api_data (source=api1)
                                    ↓
                            normalized_data

CoinGecko API → Validate → raw_api_data (source=api2)
                                    ↓
                            normalized_data

CSV File → Validate → raw_csv_data
                           ↓
                   normalized_data

RSS Feed → Parse → raw_rss_data
                        ↓
                 normalized_data
```

## Unified Data Schema

All sources are normalized to:

```python
{
    "source_type": "api1" | "api2" | "csv" | "rss",
    "source_id": "unique_id",
    "title": "Bitcoin",
    "description": "Leading cryptocurrency",
    "value": 45000.50,
    "category": "cryptocurrency",
    "tags": ["crypto", "btc"],
    "source_timestamp": "2024-01-15T10:30:00Z",
    "metadata": {
        "market_cap": 850000000000,
        "volume_24h": 28000000000,
        ...
    }
}
```

## API Limits Summary

| API | Free Tier | Rate Limit | Account Required |
|-----|-----------|------------|------------------|
| CoinPaprika | 25K calls/month | ~17/min | Yes |
| CoinGecko | Unlimited* | 10-50/min | No |
| RSS Feed | Unlimited | N/A | No |

*CoinGecko free tier has rate limiting but no hard monthly limit

## Next Steps

1. ✅ Get CoinPaprika API key from https://coinpaprika.com/api
2. ✅ Configure `.env` file with your API key
3. ✅ Test API connections with curl commands above
4. ✅ Start the ETL service: `make up`
5. ✅ Verify data ingestion: `curl http://localhost:8000/data`

---

For more information, see the main [README.md](README.md)

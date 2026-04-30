from fastapi import APIRouter, HTTPException, Query

from tradingagents.api.deps import get_config
from tradingagents.api.schemas import (
    MarketMoversResponse,
    MarketTickerDetailResponse,
    MarketWatchlistResponse,
    MarketWatchlistUpdateRequest,
    MarketWatchlistsResponse,
)
from tradingagents.markets.service import (
    get_market_detail,
    get_market_movers,
    get_watchlists_response,
    save_watchlist,
)

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/watchlists", response_model=MarketWatchlistsResponse)
def watchlists():
    return MarketWatchlistsResponse(**get_watchlists_response(get_config()))


@router.put("/watchlists/{watchlist_id}", response_model=MarketWatchlistResponse)
def update_watchlist(watchlist_id: str, request: MarketWatchlistUpdateRequest):
    try:
        return MarketWatchlistResponse(**save_watchlist(get_config(), watchlist_id, request.symbols))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/movers", response_model=MarketMoversResponse)
def movers(market: str = Query(default="all", pattern="^(pt|us|all)$")):
    try:
        return MarketMoversResponse(**get_market_movers(get_config(), market))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/tickers/{symbol}", response_model=MarketTickerDetailResponse)
def ticker_detail(symbol: str):
    return MarketTickerDetailResponse(**get_market_detail(get_config(), symbol))

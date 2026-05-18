import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from google.transit import gtfs_realtime_pb2
from google.protobuf.json_format import MessageToDict

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_STATIONS_CSV = _DATA_DIR / "stations.csv"

_MTA_BASE = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2F"

_LINE_TO_FEED = {
    "A": "gtfs-ace",
    "C": "gtfs-ace",
    "E": "gtfs-ace",
    "B": "gtfs-bdfm",
    "D": "gtfs-bdfm",
    "F": "gtfs-bdfm",
    "FX": "gtfs-bdfm",
    "M": "gtfs-bdfm",
    "G": "gtfs-g",
    "J": "gtfs-jz",
    "Z": "gtfs-jz",
    "N": "gtfs-nqrw",
    "Q": "gtfs-nqrw",
    "R": "gtfs-nqrw",
    "W": "gtfs-nqrw",
    "L": "gtfs-l",
    "1": "gtfs",
    "2": "gtfs",
    "3": "gtfs",
    "4": "gtfs",
    "5": "gtfs",
    "6": "gtfs",
    "6X": "gtfs",
    "7": "gtfs",
    "7X": "gtfs",
    "GS": "gtfs",
    "SIR": "gtfs-si",
    "SI": "gtfs-si",
}


def _load_stop_names() -> dict:
    if not _STATIONS_CSV.exists():
        return {}
    df = pd.read_csv(_STATIONS_CSV, index_col=None, header=0).set_index("stop_id")
    return df.iloc[:, 1].to_dict()


def _fetch_feed(feed_id: str, stop_names: dict) -> list:
    url = _MTA_BASE + feed_id
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(resp.content)
        data = MessageToDict(feed)
    except Exception as e:
        logger.error(f"Failed to fetch MTA feed {feed_id}: {e}")
        return []

    entities = []
    for entity in data.get("entity", []):
        try:
            trip_update = entity["tripUpdate"]
            for stop in trip_update["stopTimeUpdate"]:
                stop_id = stop.get("stopId", "")
                stop["stop_name"] = stop_names.get(stop_id, stop_id)
            entities.append(entity)
        except (KeyError, TypeError):
            pass
    return entities


def next_trains_for_station(station_info: dict, limit: int | None = 4) -> list:
    """
    Fetch only the MTA feeds relevant to the station's train lines,
    filter by the station's stop_ids, and return upcoming trains
    sorted by arrival minutes. Pass limit=None for all trains.
    """
    train_lines = station_info.get("train_lines", [])
    stop_ids = set(station_info.get("stop_ids", []))

    feeds_needed = {
        _LINE_TO_FEED[line] for line in train_lines if line in _LINE_TO_FEED
    }
    if not feeds_needed:
        logger.warning(f"No MTA feeds mapped for lines: {train_lines}")
        return []

    stop_names = _load_stop_names()

    all_entities = []
    for feed_id in feeds_needed:
        logger.debug(f"Fetching MTA feed: {feed_id}")
        all_entities.extend(_fetch_feed(feed_id, stop_names))

    now = datetime.now()
    trains = []
    for entity in all_entities:
        try:
            trip_update = entity["tripUpdate"]
            for stop in trip_update["stopTimeUpdate"]:
                if stop.get("stopId") not in stop_ids:
                    continue
                arrival_ts = stop.get("arrival", {}).get("time")
                if arrival_ts is None:
                    continue
                minutes = int(
                    (datetime.fromtimestamp(int(arrival_ts)) - now).total_seconds() / 60
                )
                if minutes < 0:
                    continue
                trains.append(
                    {
                        "route": trip_update["trip"]["routeId"],
                        "destination": trip_update["stopTimeUpdate"][-1].get(
                            "stop_name", ""
                        ),
                        "arrival_minutes": minutes,
                    }
                )
                break  # one entry per trip
        except (KeyError, TypeError, ValueError):
            pass

    trains.sort(key=lambda t: t["arrival_minutes"])
    return trains if limit is None else trains[:limit]

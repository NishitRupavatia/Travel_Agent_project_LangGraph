import os 
import re 
import certifi
import airportsdata
import pycountry
import requests
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

# Default origin when user says only destination, e.g. "Japan trip"

DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_IATA", "IN")


BASE_URL = "https://api.aviationstack.com/v1/flights"


AIRPORTS = airportsdata.load("IATA")



COUNTRY_ALIASES = {
    "usa": "US",
    "u.s.a": "US",
    "u.s.": "US",
    "america": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "england": "GB",
    "uae": "AE",
    "dubai": "AE",
    "south korea": "KR",
    "korea": "KR",
    "russia": "RU",
    "vietnam": "VN",
    "bangladesh": "BD",
    "india": "IN",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "nepal": "NP",
    "qatar": "QA",
    "saudi arabia": "SA",
    "turkey": "TR",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
}


# Preferred main airport for country-level search
COUNTRY_MAIN_AIRPORT = {
    "BD": "DAC",
    "IN": "DEL",
    "JP": "NRT",
    "US": "JFK",
    "GB": "LHR",
    "AE": "DXB",
    "SG": "SIN",
    "MY": "KUL",
    "TH": "BKK",
    "ID": "CGK",
    "CN": "PEK",
    "KR": "ICN",
    "NP": "KTM",
    "QA": "DOH",
    "SA": "JED",
    "TR": "IST",
    "CA": "YYZ",
    "AU": "SYD",
    "DE": "FRA",
    "FR": "CDG",
    "IT": "FCO",
    "ES": "MAD",
}




CITY_MAIN_AIRPORT = {
    "dhaka": "DAC",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "kolkata": "CCU",
    "chennai": "MAA",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "tokyo": "NRT",
    "osaka": "KIX",
    "kyoto": "KIX",
    "new york": "JFK",
    "london": "LHR",
    "dubai": "DXB",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bangkok": "BKK",
    "doha": "DOH",
    "istanbul": "IST",
    "toronto": "YYZ",
    "sydney": "SYD",
    "paris": "CDG",
    "rome": "FCO",
    "madrid": "MAD",
    "frankfurt": "FRA",
}


def clean_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    stop_words = [
        "flight", "flights", "ticket", "tickets", "trip", "travel",
        "plan", "complete", "days", "day", "including", "hotel",
        "hotels", "sightseeing", "under", "budget", "info", "information"
    ]
    words = [w for w in text.split() if w not in stop_words]
    return " ".join(words).strip()



def country_name_to_code(text: str):
    text = clean_text(text)

    if text in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text]

    try:
        country = pycountry.countries.lookup(text)
        return country.alpha_2
    except LookupError:
        pass

    # Detect country name inside longer text
    for country in pycountry.countries:
        country_name = country.name.lower()
        if country_name in text:
            return country.alpha_2

    for alias, code in COUNTRY_ALIASES.items():
        if alias in text:
            return code

    return None



def airport_country_matches(airport: dict, country_code: str) -> bool:
    airport_country = str(airport.get("country", "")).upper().strip()

    if airport_country == country_code:
        return True

    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if country and airport_country.lower() == country.name.lower():
            return True
    except Exception:
        pass

    return False




def get_best_airport_for_country(country_code: str):
    preferred = COUNTRY_MAIN_AIRPORT.get(country_code)

    if preferred and preferred in AIRPORTS:
        return preferred

    candidates = []

    for iata, airport in AIRPORTS.items():
        if not iata:
            continue

        if airport_country_matches(airport, country_code):
            name = str(airport.get("name", "")).lower()
            city = str(airport.get("city", "")).lower()

            score = 0

            if "international" in name:
                score += 50
            if "intl" in name:
                score += 40
            if "capital" in name:
                score += 20
            if city:
                score += 5

            candidates.append((score, iata))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]




def resolve_location_to_iata(location: str):
    """
    Converts country/city/airport/IATA into IATA code.

    Examples:
    Bangladesh -> DAC
    Japan -> NRT
    Dhaka -> DAC
    Tokyo -> NRT
    DAC -> DAC
    """

    if not location:
        return None

    raw_location = location.strip()

    # Direct IATA code
    if re.fullmatch(r"[A-Za-z]{3}", raw_location):
        code = raw_location.upper()
        if code in AIRPORTS:
            return code

    location_clean = clean_text(raw_location)

    if not location_clean:
        return None

    # City preferred airport
    if location_clean in CITY_MAIN_AIRPORT:
        return CITY_MAIN_AIRPORT[location_clean]

    # Country preferred airport
    country_code = country_name_to_code(location_clean)
    if country_code:
        airport = get_best_airport_for_country(country_code)
        if airport:
            return airport

    # Exact city match from airport database
    city_matches = []

    for iata, airport in AIRPORTS.items():
        city = str(airport.get("city", "")).lower().strip()
        name = str(airport.get("name", "")).lower().strip()

        score = 0

        if city == location_clean:
            score += 100
        elif location_clean in city:
            score += 70

        if location_clean in name:
            score += 50

        if "international" in name:
            score += 10

        if score > 0:
            city_matches.append((score, iata))

    if city_matches:
        city_matches.sort(reverse=True)
        return city_matches[0][1]

    return None




# Words that mark the location following them as an origin or a destination.
ORIGIN_MARKERS = ("from", "departing", "leaving", "starting", "origin")
DEST_MARKERS = ("to", "in", "at", "for", "visit", "visiting", "into", "towards")


def build_location_candidates():
    """
    All searchable location names, longest first so that "south korea"
    is matched before "korea".
    """
    names = set(COUNTRY_ALIASES) | set(CITY_MAIN_AIRPORT)

    for country in pycountry.countries:
        name = country.name.lower()
        if len(name) >= 4:
            names.add(name)

    return sorted(names, key=len, reverse=True)


LOCATION_CANDIDATES = build_location_candidates()


def find_location_mentions(query: str):
    """
    Finds country/city names inside a natural language query.

    Returns them in the order they appear, each tagged with the role implied
    by the word in front of it ("from Dhaka" -> origin, "to Tokyo" -> destination).

    Each item is {"text": str, "start": int, "role": "origin"|"destination"|None}.
    """

    q = query.lower()
    matches = []

    for name in LOCATION_CANDIDATES:
        for match in re.finditer(rf"\b{re.escape(name)}\b", q):
            matches.append((match.start(), match.end(), name))

    # Longest match wins wherever two names overlap ("south korea" beats "korea")
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    kept = []
    for start, end, name in matches:
        overlaps = any(start < kept_end and end > kept_start
                       for kept_start, kept_end, _ in kept)
        if not overlaps:
            kept.append((start, end, name))

    kept.sort()

    mentions = []
    for start, end, name in kept:
        words_before = q[:start].split()
        previous_word = words_before[-1] if words_before else ""

        role = None
        if previous_word in ORIGIN_MARKERS:
            role = "origin"
        elif previous_word in DEST_MARKERS:
            role = "destination"

        mentions.append({"text": name, "start": start, "role": role})

    return mentions


def parse_route(query: str):
    """
    Returns:
    dep_iata, arr_iata

    Can return:
    None, None  -> global live flights
    DAC, NRT    -> filtered route
    DAC, None   -> all flights from DAC
    None, NRT   -> all flights to NRT
    """

    q = query.strip()
    q_lower = q.lower()

    # Global / all-country query
    global_keywords = [
        "all country",
        "all countries",
        "global flight",
        "global flights",
        "all flight",
        "all flights",
        "worldwide flight",
        "worldwide flights",
    ]

    if any(keyword in q_lower for keyword in global_keywords):
        return None, None

    # Direct IATA code route: "DAC to NRT". Only trust codes that are real airports,
    # so words like "USA" are not mistaken for one.
    codes = [
        code.upper()
        for code in re.findall(r"\b[A-Z]{3}\b", q)
        if code.upper() in AIRPORTS
    ]

    if len(codes) >= 2:
        return codes[0], codes[1]

    mentions = find_location_mentions(q)

    origin_text = next(
        (m["text"] for m in mentions if m["role"] == "origin"), None
    )
    dest_text = next(
        (m["text"] for m in mentions if m["role"] == "destination"), None
    )

    # Locations with no "from"/"to" in front of them, in the order they appear
    unmarked = [m["text"] for m in mentions if m["role"] is None]

    # "Plan a Japan trip from Bangladesh" -> Japan is the unmarked destination
    if not dest_text and unmarked:
        dest_text = unmarked.pop(0)

    if not origin_text and unmarked:
        origin_text = unmarked.pop(0)

    dep_iata = resolve_location_to_iata(origin_text) if origin_text else None
    arr_iata = resolve_location_to_iata(dest_text) if dest_text else None

    # A destination with no stated origin departs from the configured home airport
    if arr_iata and not dep_iata:
        dep_iata = resolve_location_to_iata(DEFAULT_ORIGIN_IATA)

    # A route that starts and ends at the same airport is not a route
    if dep_iata and dep_iata == arr_iata:
        arr_iata = None

    return dep_iata, arr_iata


def format_flight(flight: dict):
    airline = flight.get("airline", {}).get("name") or "Unknown airline"
    flight_number = flight.get("flight", {}).get("iata") or "Unknown flight number"
    status = flight.get("flight_status") or "Unknown"

    dep = flight.get("departure", {}) or {}
    arr = flight.get("arrival", {}) or {}

    dep_airport = dep.get("airport") or "Unknown departure airport"
    dep_iata = dep.get("iata") or "Unknown"
    dep_terminal = dep.get("terminal") or "N/A"
    dep_gate = dep.get("gate") or "N/A"
    dep_scheduled = dep.get("scheduled") or "Unknown"
    dep_delay = dep.get("delay")
    dep_delay_text = f"{dep_delay} minutes" if dep_delay is not None else "N/A"

    arr_airport = arr.get("airport") or "Unknown arrival airport"
    arr_iata = arr.get("iata") or "Unknown"
    arr_terminal = arr.get("terminal") or "N/A"
    arr_gate = arr.get("gate") or "N/A"
    arr_scheduled = arr.get("scheduled") or "Unknown"
    arr_delay = arr.get("delay")
    arr_delay_text = f"{arr_delay} minutes" if arr_delay is not None else "N/A"

    return f"""
Airline: {airline}
Flight: {flight_number}
Status: {status}

Departure:
- Airport: {dep_airport}
- IATA: {dep_iata}
- Terminal: {dep_terminal}
- Gate: {dep_gate}
- Scheduled: {dep_scheduled}
- Delay: {dep_delay_text}

Arrival:
- Airport: {arr_airport}
- IATA: {arr_iata}
- Terminal: {arr_terminal}
- Gate: {arr_gate}
- Scheduled: {arr_scheduled}
- Delay: {arr_delay_text}
""".strip()


def request_flights(params: dict):
    """
    Calls the AviationStack API.
    Returns (flight_list, error_message). Exactly one of the two is meaningful.
    """

    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return None, f"Flight API request failed: {e}"
    except ValueError:
        return None, "Flight API returned invalid JSON."

    if "error" in data:
        error = data["error"]
        return None, (
            "Flight API error:\n"
            f"Code: {error.get('code', 'Unknown')}\n"
            f"Message: {error.get('message', 'Unknown error')}"
        )

    return data.get("data", []) or [], None


def describe_route(dep_iata, arr_iata):
    if dep_iata and arr_iata:
        return f"Live flights from {dep_iata} to {arr_iata}"
    if dep_iata:
        return f"Live flights from {dep_iata}"
    if arr_iata:
        return f"Live flights to {arr_iata}"
    return "Global live flights"


PRICING_NOTE = (
    "Note: AviationStack provides live flight schedules and status, not ticket prices. "
    "For actual fare prices, use a flight-pricing API such as Amadeus."
)


def search_flights(query: str, limit: int = 10):
    if not API_KEY:
        return (
            "Flight API error: AVIATIONSTACK_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "AVIATIONSTACK_API_KEY=your_api_key_here"
        )

    dep_iata, arr_iata = parse_route(query)

    params = {
        "access_key": API_KEY,
        "limit": min(limit, 100),
    }

    if dep_iata:
        params["dep_iata"] = dep_iata

    if arr_iata:
        params["arr_iata"] = arr_iata

    flight_data, error = request_flights(params)

    if error:
        return error

    header = describe_route(dep_iata, arr_iata)

    # Many city pairs have no direct flight. Rather than returning nothing useful,
    # fall back to departures from the origin and say clearly that is what happened.
    if not flight_data and dep_iata and arr_iata:
        fallback_params = {
            "access_key": API_KEY,
            "limit": min(limit, 100),
            "dep_iata": dep_iata,
        }

        flight_data, error = request_flights(fallback_params)

        if error:
            return error

        if flight_data:
            header = (
                f"No direct flights found from {dep_iata} to {arr_iata} "
                f"in the live schedule, so a connecting itinerary is likely needed.\n"
                f"Showing current departures from {dep_iata} instead"
            )

    if not flight_data:
        route_text = ""

        if dep_iata and arr_iata:
            route_text = f" for route {dep_iata} to {arr_iata}"
        elif dep_iata:
            route_text = f" from {dep_iata}"
        elif arr_iata:
            route_text = f" to {arr_iata}"

        return f"No live flight data found{route_text}.\n\n{PRICING_NOTE}"

    formatted_flights = [format_flight(flight) for flight in flight_data[:limit]]

    return (
        f"{header}\n\n"
        + "\n\n---\n\n".join(formatted_flights)
        + f"\n\n{PRICING_NOTE}"
    )


if __name__ == "__main__":
    print(search_flights("Plan a 7 days Japan trip from India"))
    print("\n" + "=" * 80 + "\n")
    print(search_flights("all country flight info"))

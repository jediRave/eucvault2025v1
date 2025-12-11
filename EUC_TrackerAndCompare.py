import requests
from bs4 import BeautifulSoup
import re
import html
import os
import webbrowser

# --------- Distributor URLs ---------
EWHEELS_BASE_URL = "https://ewheels.com"
EWHEELS_ALL_VEHICLES_URL = "https://ewheels.com/pages/all-vehicles"

ALIEN_BASE_URL = "https://alienrides.com"
ALIEN_COLLECTION_URL = "https://alienrides.com/collections/electric-unicycles"

NEXTGEN_BASE_URL = "https://nextgenmobility.org"
NEXTGEN_COLLECTION_URL = "https://nextgenmobility.org/collections/eucs"

# Keywords that probably mean "NOT an EUC"
EXCLUDE_KEYWORDS = ["scooter", "bike", "climber", "vsett", "e-bike", "e bike"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}


def clean_text(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.split()).strip()


def is_probable_euc(title: str) -> bool:
    t = title.lower()
    if any(k in t for k in EXCLUDE_KEYWORDS):
        return False
    return True


def clean_euc_name(name: str) -> str:
    """
    Remove spec info from titles like:
    - "Begode A1, 180Wh Battery/800W Motor"
    - "Begode Blitz, 2,400Wh Battery/3,500W Motor (8.5KW Peak)"
    -> "Begode A1", "Begode Blitz"
    """
    if not name:
        return ""

    name = name.strip()
    name = name.split(",")[0].strip()

    patterns = [
        r"\b\d+Wh\b.*$",
        r"\b\d+W\b.*$",
        r"\b\d+\s*MPH\b.*$",
        r"\b\d+\s*miles\b.*$",
        r"Battery.*$",
        r"Motor.*$",
    ]
    for pat in patterns:
        name = re.sub(pat, "", name, flags=re.IGNORECASE).strip()

    return name


# ---------- SCRAPERS ----------

def get_ewheels_product_links():
    print("Fetching eWheels product list...")
    resp = requests.get(EWHEELS_ALL_VEHICLES_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    links = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/products/" in href:
            title = clean_text(a.get_text())
            if not title:
                continue
            if not is_probable_euc(title):
                continue
            full_url = href if href.startswith("http") else EWHEELS_BASE_URL + href
            links.append((title, full_url))

    unique = {}
    for title, url in links:
        unique[url] = title

    print(f"eWheels: Found {len(unique)} probable EUC product pages.")
    return [
        {"name": title, "url": url, "source": "ewheels", "base_url": EWHEELS_BASE_URL}
        for url, title in unique.items()
    ]


def get_alien_product_links(max_pages: int = 10):
    """
    Scrape Alien Rides collection pages. Handles pagination via ?page=N.
    """
    print("Fetching Alien Rides product list...")
    products = {}

    for page in range(1, max_pages + 1):
        if page == 1:
            url = ALIEN_COLLECTION_URL
        else:
            url = f"{ALIEN_COLLECTION_URL}?page={page}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except Exception as e:
            print(f"  !! Error fetching Alien Rides page {page}: {e}")
            break

        if resp.status_code >= 400:
            print(f"  Alien Rides page {page} returned status {resp.status_code}, stopping.")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        found_this_page = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/products/" in href:
                title = clean_text(a.get_text())
                if not title:
                    continue
                if not is_probable_euc(title):
                    continue
                full_url = href if href.startswith("http") else ALIEN_BASE_URL + href
                products[full_url] = title
                found_this_page += 1

        print(f"  Alien Rides page {page}: found {found_this_page} product links.")
        if found_this_page == 0:
            # likely no more pages
            break

    print(f"Alien Rides: Found {len(products)} probable EUC product pages.")
    return [
        {"name": title, "url": url, "source": "alien", "base_url": ALIEN_BASE_URL}
        for url, title in products.items()
    ]


def get_nextgen_product_links(max_pages: int = 10):
    """
    Scrape NextGen Mobility collection pages. Handles pagination via ?page=N.
    """
    print("Fetching NextGen M product list...")
    products = {}

    for page in range(1, max_pages + 1):
        if page == 1:
            url = NEXTGEN_COLLECTION_URL
        else:
            url = f"{NEXTGEN_COLLECTION_URL}?page={page}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except Exception as e:
            print(f"  !! Error fetching NextGen M page {page}: {e}")
            break

        if resp.status_code >= 400:
            print(f"  NextGen M page {page} returned status {resp.status_code}, stopping.")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        found_this_page = 0

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/products/" in href:
                title = clean_text(a.get_text())
                if not title:
                    continue
                if not is_probable_euc(title):
                    continue
                full_url = href if href.startswith("http") else NEXTGEN_BASE_URL + href
                products[full_url] = title
                found_this_page += 1

        print(f"  NextGen M page {page}: found {found_this_page} product links.")
        if found_this_page == 0:
            # likely no more pages
            break

    print(f"NextGen M: Found {len(products)} probable EUC product pages.")
    return [
        {"name": title, "url": url, "source": "nextgen", "base_url": NEXTGEN_BASE_URL}
        for url, title in products.items()
    ]


def extract_stat_block(soup, label_text):
    label_text = label_text.lower()
    for node in soup.find_all(text=True):
        t = node.strip().lower()
        if t == label_text:
            parent = node.parent
            sib = parent.find_next_sibling()
            if sib:
                value = clean_text(sib.get_text())
                if value:
                    return value
    return None


def extract_battery_type_from_text(full_text: str) -> str:
    full_text = full_text.replace("\n", " ")
    m = re.search(
        r"(Samsung\s+\w+\d+|LG\s+\w+\d+|Molicel\s+\w+\d+)",
        full_text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    return "N/A"


def extract_image_url(soup) -> str:
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"]

    img = soup.find("img", src=True)
    if img:
        return img["src"]

    return ""


def extract_description(soup) -> str:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return clean_text(meta["content"])

    og = soup.find("meta", property="og:description")
    if og and og.get("content"):
        return clean_text(og["content"])

    body_text = clean_text(soup.get_text(separator=" "))
    if not body_text:
        return "No description available."

    snippet = body_text[:260]
    if len(body_text) > 260:
        snippet += "..."
    return snippet


def absolutize_url(url: str, base_url: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return base_url.rstrip("/") + url
    if base_url:
        return base_url.rstrip("/") + "/" + url.lstrip("/")
    return url


def parse_product_page(prod):
    raw_name = prod["name"]
    url = prod["url"]
    base_url = prod.get("base_url", "")
    source = prod.get("source", "ewheels")

    print(f"  -> Scraping [{source}] {raw_name} ({url})")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"     !! Error fetching {url}: {e}")
        return {
            "name": clean_euc_name(raw_name),
            "battery_capacity": "N/A",
            "range": "N/A",
            "speed": "N/A",
            "motor_power": "N/A",
            "weight": "N/A",
            "max_load": "N/A",
            "battery_type": "N/A",
            "image_url": "",
            "url": url,
            "description": "No description available.",
            "source": source,
        }

    soup = BeautifulSoup(resp.text, "html.parser")
    page_text = soup.get_text(separator=" ")

    battery_capacity = "N/A"
    range_text = "N/A"
    speed = "N/A"
    motor_power = "N/A"
    weight = "N/A"
    max_load = "N/A"

    # Try some label-based blocks (mainly useful for eWheels)
    speed_block = extract_stat_block(soup, "CRUISING SPEED")
    if not speed_block:
        speed_block = extract_stat_block(soup, "TOP SPEED")
    if speed_block:
        speed = speed_block

    weight_block = extract_stat_block(soup, "WEIGHT")
    if weight_block:
        weight = weight_block

    max_load_block = extract_stat_block(soup, "MAX LOAD")
    if max_load_block:
        max_load = max_load_block

    battery_block = extract_stat_block(soup, "BATTERY CAPACITY")
    if battery_block:
        battery_capacity = battery_block

    range_block = extract_stat_block(soup, "RANGE")
    if range_block:
        range_text = range_block

    title_h1 = soup.find("h1")
    title_text = clean_text(title_h1.get_text()) if title_h1 else raw_name

    # Battery from title / text
    if battery_capacity == "N/A":
        m = re.search(r"(\d[\d,]*)\s*Wh", title_text, re.IGNORECASE)
        if not m:
            m = re.search(r"(\d[\d,]*)\s*Wh", page_text, re.IGNORECASE)
        if m:
            battery_capacity = m.group(1).replace(",", "") + "Wh"

    # Motor power from title / text
    if motor_power == "N/A":
        m = re.search(r"(\d[\d,]*)\s*W\s*Motor", title_text, re.IGNORECASE)
        if not m:
            m = re.search(r"(\d[\d,]*)\s*W(?!h)", page_text, re.IGNORECASE)
        if m:
            motor_power = clean_text(m.group(1).replace(",", "") + "W")

    battery_type = extract_battery_type_from_text(page_text)
    image_url = absolutize_url(extract_image_url(soup), base_url)
    description = extract_description(soup)

    return {
        "name": clean_euc_name(raw_name),
        "battery_capacity": battery_capacity,
        "range": range_text,
        "speed": speed,
        "motor_power": motor_power,
        "weight": weight,
        "max_load": max_load,
        "battery_type": battery_type,
        "image_url": image_url,
        "url": url,
        "description": description,
        "source": source,
    }


def attr_escape(value: str) -> str:
    return html.escape(value or "", quote=True)


# ---------- HTML BUILDING ----------

def build_html_table(eucs):
    eucs_sorted = sorted(eucs, key=lambda x: x["name"].lower())

    # default to an eWheels wheel if available, else anything
    first = None
    for e in eucs_sorted:
        if e.get("source") == "ewheels":
            first = e
            break
    if not first:
        first = eucs_sorted[0] if eucs_sorted else {
            "name": "N/A",
            "battery_capacity": "N/A",
            "range": "N/A",
            "speed": "N/A",
            "motor_power": "N/A",
            "weight": "N/A",
            "max_load": "N/A",
            "battery_type": "N/A",
            "image_url": "",
            "url": "#",
            "description": "No wheels found.",
            "source": "ewheels",
        }

    rows_html = ""
    for e in eucs_sorted:
        rows_html += f"""
        <tr class="wheel-row"
            data-name="{attr_escape(e['name'])}"
            data-battery="{attr_escape(e['battery_capacity'])}"
            data-range="{attr_escape(e['range'])}"
            data-speed="{attr_escape(e['speed'])}"
            data-motor="{attr_escape(e['motor_power'])}"
            data-weight="{attr_escape(e['weight'])}"
            data-maxload="{attr_escape(e['max_load'])}"
            data-battype="{attr_escape(e['battery_type'])}"
            data-url="{attr_escape(e['url'])}"
            data-image="{attr_escape(e['image_url'])}"
            data-desc="{attr_escape(e['description'])}"
            data-source="{attr_escape(e.get('source', 'ewheels'))}">
            <td class="compare-col">
                <button class="compare-btn" type="button">Compare</button>
            </td>
            <td>{html.escape(e['name'])}</td>
            <td>{html.escape(e['battery_capacity'])}</td>
            <td>{html.escape(e['range'])}</td>
            <td>{html.escape(e['speed'])}</td>
            <td>{html.escape(e['motor_power'])}</td>
            <td>{html.escape(e['weight'])}</td>
            <td>{html.escape(e['max_load'])}</td>
            <td>{html.escape(e['battery_type'])}</td>
        </tr>
        """

    first_source = first.get("source", "ewheels")
    if first_source == "alien":
        first_source_label = "Alien Rides – Electric Unicycles"
    elif first_source == "nextgen":
        first_source_label = "NextGen M – EUCs"
    else:
        first_source_label = "eWheels – All Vehicles"

    context = {
        "ROWS_HTML": rows_html,
        "SUBTITLE_SOURCE_LABEL": html.escape(first_source_label),
        "SEL_NAME": html.escape(first["name"]),
        "SEL_BATTYPE": html.escape(first.get("battery_type") or "Battery Type N/A"),
        "SEL_DESC": html.escape(first.get("description") or "No description available."),
        "SEL_BATTERY": html.escape(first.get("battery_capacity") or "N/A"),
        "SEL_RANGE": html.escape(first.get("range") or "N/A"),
        "SEL_SPEED": html.escape(first.get("speed") or "N/A"),
        "SEL_MOTOR": html.escape(first.get("motor_power") or "N/A"),
        "SEL_WEIGHT": html.escape(first.get("weight") or "N/A"),
        "SEL_MAXLOAD": html.escape(first.get("max_load") or "N/A"),
        "SEL_URL": html.escape(first.get("url") or "#"),
        "FIRST_SOURCE": first_source,
    }

    template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>EUC Vault – Multi-Distributor</title>
    <style>
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: #020617;
            color: #e5e7eb;
            padding: 0;
            margin: 0;
        }

        /* Top menu bar */
        .topbar {
            position: sticky;
            top: 0;
            z-index: 40;
            background: #020617;
            border-bottom: 1px solid #1f2937;
            overflow: visible; /* allow logo to overhang */
        }
        .topbar-inner {
            max-width: 1200px;
            margin: 0 auto;
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
        }
        .topbar-left {
            position: relative; /* anchor for overhang logo */
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.95rem;
            font-weight: 600;
            color: #e5e7eb;
            white-space: nowrap;
        }

        /* Overhang logo wrapper */
        .logo-overhang {
            position: absolute;
            left: 0;
            bottom: -45px;  /* how far logo hangs below the bar */
        }

        /* Logo itself */
        .navbar-logo {
            height: 64px;  /* adjust for bigger/smaller badge */
            width: auto;
            display: block;
        }

        /* Text next to logo */
        .topbar-title {
            margin-left: 80px; /* push text to the right of the logo */
        }

        .topbar-links {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .topbar-link {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 6px 14px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            font-size: 0.85rem;
            font-weight: 600;
            text-decoration: none;
            color: #e5e7eb;
            background: #0f172a;
            white-space: nowrap;
            cursor: pointer;
        }
        .topbar-link-active {
            background: #0ea5e9;
            color: #f9fafb;
            opacity: 1;
        }
        .topbar-link-disabled {
            opacity: 0.5;
        }

        /* Search area in top bar */
        .topbar-right {
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }
        .topbar-search {
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }
        #range-monitor-btn {
            padding: 6px 14px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #22c55e;   /* green-ish, you can tweak */
            color: #0b1120;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }

        #range-monitor-btn:hover {
            background: #16a34a;
        }

        #name-search-input {
            padding: 4px 8px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #020617;
            color: #e5e7eb;
            font-size: 0.8rem;
            min-width: 160px;
        }
        #name-search-select {
            padding: 4px 8px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #020617;
            color: #e5e7eb;
            font-size: 0.8rem;
            max-width: 220px;
        }
        #name-search-btn {
            padding: 5px 12px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #22c55e;
            color: #0b1120;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
        }

        h1 {
            color: #38bdf8;
        }
        .subtitle {
            color: #9ca3af;
            margin-bottom: 1rem;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin-top: 1rem;
            font-size: 0.9rem;
        }
        th, td {
            border: 1px solid #1f2937;
            padding: 8px 10px;
            text-align: left;
        }
        th {
            background: #0f172a;
            position: sticky;
            top: 0;
            z-index: 1;
        }
        tr:nth-child(even) {
            background: #020617;
        }
        tr:nth-child(odd) {
            background: #020617;
        }
        tr:hover {
            background: #111827;
        }
        .active-row {
            background: #1d283a !important;
        }
        .name-col {
            min-width: 220px;
            font-weight: 600;
        }
        .small {
            font-size: 0.8rem;
            color: #6b7280;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        a {
            color: #38bdf8;
        }
        .selected-wrapper {
            display: flex;
            gap: 20px;
            align-items: stretch;
            background: #020617;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 16px;
            margin-top: 16px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.4);
            position: sticky;
            top: 56px;
            z-index: 20;
        }
        .selected-image-box {
            width: 260px;
            min-height: 180px;
            background: radial-gradient(circle at top, #1e293b, #020617);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .selected-image-box img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        .no-image {
            color: #6b7280;
            font-size: 0.9rem;
            text-align: center;
            padding: 20px;
        }
        .selected-info {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .selected-title {
            font-size: 1.4rem;
            font-weight: 700;
        }
        .selected-desc {
            font-size: 0.9rem;
            color: #9ca3af;
            margin-top: 4px;
        }
        /* UPDATED: tighter grid so all specs fit on one line */
        .selected-specs {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 4px 10px;
            margin-top: 8px;
        }
        .spec-label {
            font-size: 0.8rem;
            color: #9ca3af;
        }
        .spec-value {
            font-size: 0.95rem;
            font-weight: 500;
        }
        .view-link {
            margin-top: 10px;
            font-size: 0.9rem;
        }
        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            background: #0f172a;
            border: 1px solid #1f2937;
            font-size: 0.75rem;
            color: #9ca3af;
        }
        .selected-actions {
            margin-top: 8px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        #compare-toggle-btn {
            padding: 6px 14px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #0ea5e9;
            color: #f9fafb;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
        }
        #compare-toggle-btn.active {
            background: #22c55e;
        }
        #feedback-btn,
        .cmp-feedback-btn {
            padding: 6px 14px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #111827;
            color: #e5e7eb;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
        }
        #feedback-btn:hover,
        .cmp-feedback-btn:hover {
            background: #1f2937;
        }
        .compare-col {
            width: 90px;
            text-align: center;
        }
        .compare-btn {
            display: none;
            padding: 4px 8px;
            border-radius: 6px;
            border: none;
            background: #f97316;
            color: #111827;
            font-size: 0.78rem;
            font-weight: 700;
            cursor: pointer;
        }
        .compare-btn.show {
            display: inline-block;
        }

        /* --- COMPACT COMPARE BANNER --- */
        .compare-wrapper {
            display: none;
            gap: 14px;
            align-items: center;
            background: #020617;
            border: 1px solid #1f2937;
            border-radius: 10px;
            padding: 10px 14px;
            margin-top: 10px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.3);
            position: sticky;
            top: 240px;
            z-index: 19;
        }
        .compare-wrapper .selected-image-box {
            width: 110px;
            min-height: 110px;
            max-height: 110px;
            border-radius: 10px;
        }
        .compare-wrapper .selected-title {
            font-size: 1.05rem;
            margin-bottom: 2px;
        }
        .compare-wrapper .selected-info {
            gap: 4px;
        }

        .compare-specs-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 4px 12px;
            margin-top: 4px;
        }
        .compare-spec-block {
            font-size: 0.8rem;
        }
        .compare-spec-block .spec-label {
            font-size: 0.75rem;
        }
        .spec-main {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .spec-bar {
            height: 4px;
            border-radius: 999px;
            background: #020617;
            overflow: hidden;
            border: 1px solid #111827;
        }
        .spec-bar-fill {
            height: 100%;
            width: 0%;
            background: linear-gradient(90deg, #22c55e, #0ea5e9);
            transition: width 0.25s ease-out;
        }

        .compare-banner-btn {
            padding: 6px 14px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #f97316;
            color: #111827;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
        }
        .compare-clear-btn {
            margin-left: 4px;
            padding: 6px 14px;
            border-radius: 999px;
            border: 1px solid #1f2937;
            background: #ef4444;
            color: #f9fafb;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
        }

        .feedback-modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(15,23,42,0.85);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 50;
        }
        .feedback-modal {
            background: #020617;
            border-radius: 12px;
            border: 1f2937;
            max-width: 600px;
            width: 90%;
            max-height: 70vh;
            padding: 16px 20px;
            box-shadow: 0 15px 40px rgba(0,0,0,0.7);
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .feedback-modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
        }
        .feedback-modal-title {
            font-size: 1rem;
            font-weight: 600;
        }
        .feedback-modal-wheel {
            font-size: 0.85rem;
            color: #9ca3af;
        }
        .feedback-close-btn {
            border: none;
            background: #111827;
            color: #e5e7eb;
            border-radius: 999px;
            width: 28px;
            height: 28px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .feedback-close-btn:hover {
            background: #1f2937;
        }
        .feedback-list {
            margin: 0;
            padding: 0;
            list-style: none;
            overflow-y: auto;
            flex: 1;
            border-top: 1px solid #111827;
            border-bottom: 1px solid #111827;
            margin-top: 8px;
            margin-bottom: 8px;
        }
        .feedback-item {
            font-size: 0.9rem;
            padding: 6px 0;
            border-bottom: 1px solid #020617;
        }

        /* Range Monitor modal */
        .range-modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(15,23,42,0.85);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 60;
        }
        .range-modal {
            background: #020617;
            border-radius: 12px;
            border: 1px solid #1f2937;
            max-width: 1100px;
            width: 95%;
            max-height: 80vh;
            padding: 12px 14px;
            box-shadow: 0 15px 40px rgba(0,0,0,0.7);
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .range-modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            margin-bottom: 4px;
        }
        .range-modal-title {
            font-size: 1rem;
            font-weight: 600;
        }
        .range-close-btn {
            border: none;
            background: #111827;
            color: #e5e7eb;
            border-radius: 999px;
            width: 28px;
            height: 28px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .range-close-btn:hover {
            background: #1f2937;
        }
        .range-modal-body {
            flex: 1;
            min-height: 480px;
            overflow: hidden;
            border-radius: 8px;
            border: 1px solid #111827;
        }
        .range-modal-body iframe {
            width: 100%;
            height: 100%;
            border: none;
            background: #020617;
        }
    </style>
</head>
<body>

<div class="topbar">
    <div class="topbar-inner">
        <div class="topbar-left">
            <div class="logo-overhang">
                <img src="EUCVault_Logo.png" class="navbar-logo" alt="EUC Vault Logo">
            </div>
        </div>
        <div class="topbar-links">
            <button class="topbar-link topbar-link-active"
                    type="button"
                    data-distributor="ewheels">
                eWheels
            </button>
            <button class="topbar-link topbar-link-disabled"
                    type="button"
                    data-distributor="alien">
                Alien Rides
            </button>
            <button class="topbar-link topbar-link-disabled"
                    type="button"
                    data-distributor="nextgen">
                NextGen M
            </button>
        </div>
        <div class="topbar-right">
            <div class="topbar-search">
                <input id="name-search-input" type="text" placeholder="Search wheel name..." />
                <select id="name-search-select">
                    <option value="">Or pick a wheel…</option>
                </select>
                <button id="name-search-btn" type="button">Search</button>
            </div>
        </div>
    </div>
</div>

<div class="container">
    <h1>EUC Vault Table</h1>
    <div class="subtitle">
        Data scraped from <span id="subtitle-source-label">__SUBTITLE_SOURCE_LABEL__</span>.
        Missing or unavailable values are shown as <strong>N/A</strong>.
    </div>

    <!-- MAIN selected wheel banner (pinned) -->
    <div class="selected-wrapper" id="selected-wrapper">
        <div class="selected-image-box" id="selected-image-box"></div>
        <div class="selected-info">
            <div class="selected-title" id="sel-name">__SEL_NAME__</div>
            <div class="badge" id="sel-battype-badge">__SEL_BATTYPE__</div>
            <div class="selected-desc" id="sel-desc">__SEL_DESC__</div>
            <div class="selected-specs">
                <div>
                    <div class="spec-label">Battery</div>
                    <div class="spec-value" id="sel-battery">__SEL_BATTERY__</div>
                </div>
                <div>
                    <div class="spec-label">Range</div>
                    <div class="spec-value" id="sel-range">__SEL_RANGE__</div>
                </div>
                <div>
                    <div class="spec-label">Top Speed</div>
                    <div class="spec-value" id="sel-speed">__SEL_SPEED__</div>
                </div>
                <div>
                    <div class="spec-label">Motor Power</div>
                    <div class="spec-value" id="sel-motor">__SEL_MOTOR__</div>
                </div>
                <div>
                    <div class="spec-label">Weight</div>
                    <div class="spec-value" id="sel-weight">__SEL_WEIGHT__</div>
                </div>
                <div>
                    <div class="spec-label">Max Load</div>
                    <div class="spec-value" id="sel-maxload">__SEL_MAXLOAD__</div>
                </div>
            </div>

            <div class="selected-actions">
                <button id="compare-toggle-btn" type="button">Compare EUC</button>

                <!-- Range Monitor button -->
                <button id="range-monitor-btn" type="button">
                    Range Monitor
                </button>

                <button id="feedback-btn" type="button">
                    What do others say about this wheel?
                </button>
            </div>

            <div class="view-link">
                <a href="__SEL_URL__" target="_blank" id="sel-url">
                    View this wheel →
                </a>
            </div>
        </div>
    </div>

    <!-- COMPACT comparison popup banner (starts hidden) -->
    <div class="compare-wrapper" id="compare-wrapper">
        <div class="selected-image-box" id="cmp-image-box"></div>
        <div class="selected-info">
            <div class="selected-title" id="cmp-name">Comparison EUC</div>
            <div class="badge" id="cmp-battype-badge">Battery Type N/A</div>

            <div class="compare-specs-grid">
                <div class="compare-spec-block">
                    <div class="spec-label">Battery</div>
                    <div class="spec-main">
                        <span class="spec-value" id="cmp-battery">N/A</span>
                        <div class="spec-bar"><div class="spec-bar-fill" id="cmp-battery-bar"></div></div>
                    </div>
                </div>
                <div class="compare-spec-block">
                    <div class="spec-label">Range</div>
                    <div class="spec-main">
                        <span class="spec-value" id="cmp-range">N/A</span>
                        <div class="spec-bar"><div class="spec-bar-fill" id="cmp-range-bar"></div></div>
                    </div>
                </div>
                <div class="compare-spec-block">
                    <div class="spec-label">Top Speed</div>
                    <div class="spec-main">
                        <span class="spec-value" id="cmp-speed">N/A</span>
                        <div class="spec-bar"><div class="spec-bar-fill" id="cmp-speed-bar"></div></div>
                    </div>
                </div>
                <div class="compare-spec-block">
                    <div class="spec-label">Motor Power</div>
                    <div class="spec-main">
                        <span class="spec-value" id="cmp-motor">N/A</span>
                        <div class="spec-bar"><div class="spec-bar-fill" id="cmp-motor-bar"></div></div>
                    </div>
                </div>
                <div class="compare-spec-block">
                    <div class="spec-label">Weight</div>
                    <div class="spec-main">
                        <span class="spec-value" id="cmp-weight">N/A</span>
                        <div class="spec-bar"><div class="spec-bar-fill" id="cmp-weight-bar"></div></div>
                    </div>
                </div>
                <div class="compare-spec-block">
                    <div class="spec-label">Max Load</div>
                    <div class="spec-main">
                        <span class="spec-value" id="cmp-maxload">N/A</span>
                        <div class="spec-bar"><div class="spec-bar-fill" id="cmp-maxload-bar"></div></div>
                    </div>
                </div>
            </div>

            <div class="selected-actions">
                <button class="compare-banner-btn" type="button">Compare</button>
                <button class="compare-clear-btn" type="button">Remove</button>
                <button class="cmp-feedback-btn" type="button">
                    What do others say about this wheel?
                </button>
            </div>
            <div class="view-link">
                <a href="#" target="_blank" id="cmp-url">View this wheel →</a>
            </div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th class="compare-col">Compare</th>
                <th class="name-col">EUC Name</th>
                <th>Battery Capacity</th>
                <th>Range</th>
                <th>Speed</th>
                <th>Motor Power</th>
                <th>Weight</th>
                <th>Max Load</th>
                <th>Battery Type</th>
            </tr>
        </thead>
        <tbody id="euc-tbody">
            __ROWS_HTML__
        </tbody>
    </table>
    <p class="small">
        NOTE: This is a best-effort scraper. Always double-check critical specs on the original product pages before buying.
    </p>
</div>

<div class="feedback-modal-overlay" id="feedback-overlay">
    <div class="feedback-modal" id="feedback-modal">
        <div class="feedback-modal-header">
            <div>
                <div class="feedback-modal-title">What others say about this wheel</div>
                <div class="feedback-modal-wheel" id="feedback-wheel-name"></div>
            </div>
            <button class="feedback-close-btn" id="feedback-close-btn" type="button">✕</button>
        </div>
        <ul class="feedback-list" id="feedback-list"></ul>
    </div>
</div>

<!-- RANGE MONITOR MODAL -->
<div class="range-modal-overlay" id="range-overlay">
    <div class="range-modal">
        <div class="range-modal-header">
            <div class="range-modal-title">Range Monitor</div>
            <button class="range-close-btn" id="range-close-btn" type="button">✕</button>
        </div>
        <div class="range-modal-body">
            <!-- src is set in JS on first open -->
            <iframe id="range-iframe" src="" frameborder="0"></iframe>
        </div>
    </div>
</div>

<script>
    let compareMode = false;
    let currentSource = "__FIRST_SOURCE__";  // "ewheels", "alien", or "nextgen"

    // holds the currently selected wheel data (full, for UI)
    let currentWheelPayload = null;

    // numeric preset for the Range Monitor page
    let currentRangePreset = null;

    // Will hold a reference to the external window (file:// fallback)
    let rangeMonitorWindow = null;

    const FEEDBACK_DATA = {
        "Begode A1": [
            "Super portable and fun for short city rides.",
            "Great starter wheel but range is limited.",
            "Riders say the pedals are comfy for the size.",
            "Can feel twitchy at higher speeds, stay conservative.",
            "Perfect for tossing in the trunk as a backup EUC."
        ],
        "Begode EX.N": [
            "Monster torque and great for hills.",
            "Heavy, but stable at cruising speed.",
            "Some riders recommend upgrading the pads and pedals.",
            "Range is solid, especially at moderate speeds.",
            "Keep an eye on shell/handle screws if you ride hard."
        ],
        "_default": [
            "Riders describe this wheel as a solid all-rounder.",
            "Comfort and pedal feel are often praised.",
            "Community feedback notes that firmware can change ride feel.",
            "Many recommend quality safety gear with this wheel.",
            "Check community threads for long-term durability reports."
        ]
    };

    let currentFeedbackWheel = "";
    let currentFeedbackList = [];

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function renderFeedbackList() {
        const listEl = document.getElementById('feedback-list');
        listEl.innerHTML = "";
        currentFeedbackList.forEach(text => {
            const li = document.createElement('li');
            li.className = 'feedback-item';
            li.textContent = text;
            listEl.appendChild(li);
        });
    }

    function openFeedbackModal(wheelName) {
        currentFeedbackWheel = wheelName || "This wheel";
        currentFeedbackList = FEEDBACK_DATA[wheelName] || FEEDBACK_DATA["_default"];

        const nameEl = document.getElementById('feedback-wheel-name');
        const overlay = document.getElementById('feedback-overlay');

        nameEl.textContent = currentFeedbackWheel;
        renderFeedbackList();

        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function closeFeedbackModal() {
        const overlay = document.getElementById('feedback-overlay');
        overlay.style.display = 'none';
        document.body.style.overflow = '';
    }

    // ------------- numeric parsing helpers (for Range Monitor & spec bars) -------------

    function parseFirstNumber(str) {
        if (!str) return null;
        const nums = String(str).match(/(\d+(\.\d+)?)/g);
        if (!nums || !nums.length) return null;
        return parseFloat(nums[0]);
    }

    function parseLargestNumber(str) {
        if (!str) return null;
        const nums = String(str).match(/(\d+(\.\d+)?)/g);
        if (!nums || !nums.length) return null;
        return nums
            .map(parseFloat)
            .filter(v => !Number.isNaN(v))
            .reduce((a, b) => Math.max(a, b), -Infinity);
    }

    function parseBatteryWh(batteryStr) {
        if (!batteryStr) return 3600; // fallback
        const m = batteryStr.match(/(\d[\d,]*)\s*Wh/i);
        if (m) {
            return parseInt(m[1].replace(/,/g, ""), 10);
        }
        const n = parseFirstNumber(batteryStr);
        return n || 3600;
    }

    function parseRangeMiles(rangeStr) {
        if (!rangeStr) return 40;
        const nums = String(rangeStr).match(/(\d+(\.\d+)?)/g);
        if (!nums || !nums.length) return 40;

        const values = nums.map(parseFloat).filter(v => !Number.isNaN(v));
        if (!values.length) return 40;

        // If two numbers with dash / "to" → average
        if (values.length === 2 && /-|–|to/i.test(rangeStr)) {
            return (values[0] + values[1]) / 2;
        }

        // Else largest number
        const max = values.reduce((a, b) => Math.max(a, b), values[0]);
        return max;
    }

    function parseSpeedMph(speedStr) {
        if (!speedStr) return 30;

        const mphMatches = [];
        const re = /(\d+(\.\d+)?)\s*mph/gi;
        let m;
        while ((m = re.exec(speedStr)) !== null) {
            mphMatches.push(parseFloat(m[1]));
        }
        if (mphMatches.length) {
            return mphMatches.reduce((a, b) => Math.max(a, b), mphMatches[0]);
        }

        const n = parseLargestNumber(speedStr);
        return n || 30;
    }

    function parseWeightLbs(weightStr) {
        if (!weightStr) return 90;

        const re = /(\d+(\.\d+)?)\s*(lb|lbs)/gi;
        const matches = [];
        let m;
        while ((m = re.exec(weightStr)) !== null) {
            matches.push(parseFloat(m[1]));
        }
        if (matches.length) {
            return matches.reduce((a, b) => Math.max(a, b), matches[0]);
        }

        const n = parseLargestNumber(weightStr);
        return n || 90;
    }

    function parseMotorW(motorStr) {
        if (!motorStr) return 2000;
        const m = String(motorStr).match(/(\d[\d,]*)\s*W\b/i);
        if (m) {
            return parseInt(m[1].replace(/,/g, ""), 10);
        }
        const n = parseLargestNumber(motorStr);
        return n || 2000;
    }

    function buildWheelPayloadFromRow(row) {
        if (!row) return null;
        return {
            name: row.dataset.name || 'N/A',
            battery: row.dataset.battery || 'N/A',
            range: row.dataset.range || 'N/A',
            speed: row.dataset.speed || 'N/A',
            motor: row.dataset.motor || 'N/A',
            weight: row.dataset.weight || 'N/A',
            maxload: row.dataset.maxload || 'N/A',
            battype: row.dataset.battype || 'N/A',
            source: row.dataset.source || 'ewheels',
            url: row.dataset.url || '#'
        };
    }

    // UPDATED: numeric preset for the Range Monitor page, including imageUrl
    function buildRangePresetFromRow(row) {
        if (!row) return null;

        const name    = row.dataset.name   || 'N/A';
        const battery = row.dataset.battery || '';
        const range   = row.dataset.range   || '';
        const speed   = row.dataset.speed   || '';
        const weight  = row.dataset.weight  || '';
        const image   = row.dataset.image   || '';

        const batteryWh    = parseBatteryWh(battery);
        const claimedRange = parseRangeMiles(range);
        const topSpeed     = parseSpeedMph(speed);
        const wheelWeight  = parseWeightLbs(weight);

        // Rider weight is a user thing; we just give a sane default
        const riderWeight  = 180;

        return {
            wheelName: name,
            batteryWh: batteryWh,
            claimedRange: claimedRange,
            topSpeed: topSpeed,
            wheelWeight: wheelWeight,
            riderWeight: riderWeight,
            // this is what the Range Monitor page will use to show the wheel image
            imageUrl: image
        };
    }

    // NEW: send the current wheel preset to the Range Monitor (iframe or external window)
    function sendWheelToRangeMonitor() {
        if (!currentRangePreset) return;

        const message = {
            type: "EUC_RANGE_SYNC",
            payload: currentRangePreset
        };

        const iframe = document.getElementById('range-iframe');

        // If the iframe exists and is loaded, use postMessage
        if (iframe && iframe.contentWindow) {
            iframe.contentWindow.postMessage(message, "*");
        }

        // Also try posting to the external window (file:// fallback)
        if (rangeMonitorWindow && !rangeMonitorWindow.closed) {
            rangeMonitorWindow.postMessage(message, "*");
        }
    }

    function openRangeModal() {
        const overlay = document.getElementById('range-overlay');
        const iframe  = document.getElementById('range-iframe');
        if (!overlay || !iframe) return;

        const isHttp = (location.protocol === 'http:' || location.protocol === 'https:');

        if (isHttp) {
            // Ensure we have a load handler bound once, BEFORE setting src
            if (!iframe.dataset.bound) {
                iframe.addEventListener('load', function() {
                    sendWheelToRangeMonitor();
                });
                iframe.dataset.bound = '1';
            }

            // When served over HTTP(S), load inside the iframe (once)
            if (!iframe.dataset.loaded) {
                iframe.src = 'euc_realistic_range.html';  // relative to euc_table.html
                iframe.dataset.loaded = '1';
            } else {
                // Already loaded, just send the current wheel
                sendWheelToRangeMonitor();
            }

            overlay.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        } else {
            // file:// fallback
            rangeMonitorWindow = window.open('euc_realistic_range.html', 'EUC_RangeMonitor');

            setTimeout(function() {
                try {
                    sendWheelToRangeMonitor();
                } catch (err) {
                    // ignore if window not ready
                }
            }, 700);
        }
    }

    function closeRangeModal() {
        const overlay = document.getElementById('range-overlay');
        if (!overlay) return;

        overlay.style.display = 'none';
        document.body.style.overflow = '';
    }

    function siteLabelForSource(source) {
        if (source === 'alien') return 'Alien Rides';
        if (source === 'nextgen') return 'NextGen M';
        return 'eWheels';
    }

    function updateSubtitle() {
        const label = document.getElementById('subtitle-source-label');
        if (!label) return;
        if (currentSource === 'alien') {
            label.textContent = 'Alien Rides – Electric Unicycles';
        } else if (currentSource === 'nextgen') {
            label.textContent = 'NextGen M – EUCs';
        } else {
            label.textContent = 'eWheels – All Vehicles';
        }
    }

    function updateSelected(row) {
        document.querySelectorAll('.wheel-row').forEach(r => r.classList.remove('active-row'));
        row.classList.add('active-row');

        const name = row.dataset.name || 'N/A';
        const battery = row.dataset.battery || 'N/A';
        const range = row.dataset.range || 'N/A';
        const speed = row.dataset.speed || 'N/A';
        const motor = row.dataset.motor || 'N/A';
        const weight = row.dataset.weight || 'N/A';
        const maxload = row.dataset.maxload || 'N/A';
        const battype = row.dataset.battype || 'Battery Type N/A';
        const url = row.dataset.url || '#';
        const image = row.dataset.image || '';
        const desc = row.dataset.desc || 'No description available.';
        const source = row.dataset.source || 'ewheels';

        document.getElementById('sel-name').textContent = name;
        document.getElementById('sel-battery').textContent = battery;
        document.getElementById('sel-range').textContent = range;
        document.getElementById('sel-speed').textContent = speed;
        document.getElementById('sel-motor').textContent = motor;
        document.getElementById('sel-weight').textContent = weight;
        document.getElementById('sel-maxload').textContent = maxload;
        document.getElementById('sel-battype-badge').textContent = battype || 'Battery Type N/A';
        document.getElementById('sel-desc').textContent = desc;

        const link = document.getElementById('sel-url');
        link.href = url;
        link.textContent = 'View this wheel → (' + siteLabelForSource(source) + ')';

        const imgBox = document.getElementById('selected-image-box');
        imgBox.innerHTML = '';
        if (image) {
            const img = document.createElement('img');
            img.src = image;
            img.alt = name;
            imgBox.appendChild(img);
        } else {
            const div = document.createElement('div');
            div.className = 'no-image';
            div.textContent = 'No image available';
            imgBox.appendChild(div);
        }

        // update globals for Range Monitor + other use
        currentWheelPayload = buildWheelPayloadFromRow(row);
        currentRangePreset  = buildRangePresetFromRow(row);
    }

    function setSpecBar(id, value, maxVal) {
        const el = document.getElementById(id);
        if (!el) return;
        if (value == null || !isFinite(value)) {
            el.style.width = '0%';
            return;
        }
        let pct = (value / maxVal) * 100;
        pct = Math.max(5, Math.min(100, pct));
        el.style.width = pct + '%';
    }

    function updateCompareBanner(row) {
        if (!compareMode) return;

        const wrapper = document.getElementById('compare-wrapper');
        if (!wrapper) return;
        wrapper.style.display = 'flex';

        const name = row.dataset.name || 'N/A';
        const battery = row.dataset.battery || 'N/A';
        const range = row.dataset.range || 'N/A';
        const speed = row.dataset.speed || 'N/A';
        const motor = row.dataset.motor || 'N/A';
        const weight = row.dataset.weight || 'N/A';
        const maxload = row.dataset.maxload || 'N/A';
        const battype = row.dataset.battype || 'Battery Type N/A';
        const url = row.dataset.url || '#';
        const image = row.dataset.image || '';
        const source = row.dataset.source || 'ewheels';

        document.getElementById('cmp-name').textContent = name;
        document.getElementById('cmp-battery').textContent = battery;
        document.getElementById('cmp-range').textContent = range;
        document.getElementById('cmp-speed').textContent = speed;
        document.getElementById('cmp-motor').textContent = motor;
        document.getElementById('cmp-weight').textContent = weight;
        document.getElementById('cmp-maxload').textContent = maxload;
        document.getElementById('cmp-battype-badge').textContent = battype || 'Battery Type N/A';

        const link = document.getElementById('cmp-url');
        link.href = url;
        link.textContent = 'View this wheel → (' + siteLabelForSource(source) + ')';

        const imgBox = document.getElementById('cmp-image-box');
        imgBox.innerHTML = '';
        if (image) {
            const img = document.createElement('img');
            img.src = image;
            img.alt = name;
            imgBox.appendChild(img);
        } else {
            const div = document.createElement('div');
            div.className = 'no-image';
            div.textContent = 'No image available';
            imgBox.appendChild(div);
        }

        // numeric values for level bars
        const batteryWh = parseBatteryWh(battery);
        const rangeMi   = parseRangeMiles(range);
        const speedMph  = parseSpeedMph(speed);
        const motorW    = parseMotorW(motor);
        const weightLb  = parseWeightLbs(weight);
        const maxLoadLb = parseWeightLbs(maxload);

        // rough maxes for normalization – tweak as you like
        setSpecBar('cmp-battery-bar', batteryWh, 4000);
        setSpecBar('cmp-range-bar',   rangeMi,   120);
        setSpecBar('cmp-speed-bar',   speedMph,  55);
        setSpecBar('cmp-motor-bar',   motorW,    4000);
        setSpecBar('cmp-weight-bar',  weightLb,  120);
        setSpecBar('cmp-maxload-bar', maxLoadLb, 350);
    }

    function setCompareMode(on) {
        compareMode = on;

        document.querySelectorAll('.compare-btn').forEach(btn => {
            if (compareMode) {
                btn.classList.add('show');
            } else {
                btn.classList.remove('show');
            }
        });

        const toggle = document.getElementById('compare-toggle-btn');
        if (toggle) {
            toggle.textContent = compareMode ? 'Compare EUC (On)' : 'Compare EUC';
            toggle.classList.toggle('active', compareMode);
        }

        const wrapper = document.getElementById('compare-wrapper');
        if (wrapper && !compareMode) {
            wrapper.style.display = 'none';
        }
    }

    function applySourceFilter() {
        const rows = document.querySelectorAll('.wheel-row');
        rows.forEach(row => {
            if (row.dataset.source === currentSource) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    }

    function firstVisibleRowForCurrentSource() {
        const rows = document.querySelectorAll('.wheel-row');
        for (const row of rows) {
            if (row.dataset.source === currentSource) {
                return row;
            }
        }
        return null;
    }

    function setSource(newSource) {
        currentSource = newSource || 'ewheels';

        // Toggle topbar button styles
        document.querySelectorAll('.topbar-link').forEach(btn => {
            const src = btn.dataset.distributor;
            const active = (src === currentSource);
            btn.classList.toggle('topbar-link-active', active);
            btn.classList.toggle('topbar-link-disabled', !active);
        });

        applySourceFilter();
        updateSubtitle();

        const row = firstVisibleRowForCurrentSource();
        if (row) {
            updateSelected(row);
        } else {
            const imgBox = document.getElementById('selected-image-box');
            if (imgBox) {
                imgBox.innerHTML = '<div class="no-image">No wheels found</div>';
            }
            const desc = document.getElementById('sel-desc');
            if (desc) {
                desc.textContent = 'No wheels found for this distributor.';
            }
            currentWheelPayload = null;
            currentRangePreset  = null;
        }
    }

    // -------- Helper: collect rows as plain objects --------

    function buildRowData(row) {
        return {
            name: row.dataset.name || 'N/A',
            battery: row.dataset.battery || 'N/A',
            range: row.dataset.range || 'N/A',
            speed: row.dataset.speed || 'N/A',
            motor: row.dataset.motor || 'N/A',
            weight: row.dataset.weight || 'N/A',
            maxload: row.dataset.maxload || 'N/A',
            battype: row.dataset.battype || 'N/A',
            source: row.dataset.source || 'ewheels',
            url: row.dataset.url || '#'
        };
    }

    function getAllRowsData() {
        const rows = document.querySelectorAll('.wheel-row');
        return Array.from(rows).map(buildRowData);
    }

    function collectUniqueNames() {
        const rows = document.querySelectorAll('.wheel-row');
        const namesSet = new Set();
        rows.forEach(row => {
            const n = (row.dataset.name || '').trim();
            if (n) namesSet.add(n);
        });
        return Array.from(namesSet).sort((a, b) => a.localeCompare(b));
    }

    // -------- Search results window --------

    function openSearchResultsPage(allRowsData, initialQueryLabel, initialQueryValue) {
        const win = window.open('', '_blank');
        if (!win) {
            alert('Popup blocked. Please allow popups for this site to see search results.');
            return;
        }
        const doc = win.document;

        const names = Array.from(new Set(allRowsData.map(r => r.name))).sort();

        doc.open();
        doc.write('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>EUC Search Results</title>');
        doc.write('<style>');
        doc.write('body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#020617;color:#e5e7eb;margin:0;padding:0;}');
        doc.write('.topbar{position:sticky;top:0;z-index:40;background:#020617;border-bottom:1px solid #1f2937;overflow:visible;}');
        doc.write('.topbar-inner{max-width:1200px;margin:0 auto;padding:10px 20px;display:flex;align-items:center;justify-content:space-between;gap:16px;}');
        doc.write('.topbar-left{position:relative;display:flex;align-items:center;gap:8px;font-size:0.95rem;font-weight:600;color:#e5e7eb;white-space:nowrap;}');
        doc.write('.logo-overhang{position:absolute;left:0;bottom:-35px;}');
        doc.write('.navbar-logo{height:64px;width:auto;display:block;}');
        doc.write('.topbar-title{margin-left:80px;}');
        doc.write('.topbar-links{display:flex;align-items:center;gap:10px;}');
        doc.write('.topbar-link{display:inline-flex;align-items:center;justify-content:center;padding:6px 14px;border-radius:999px;border:1px solid #1f2937;font-size:0.85rem;font-weight:600;text-decoration:none;color:#e5e7eb;background:#0f172a;white-space:nowrap;cursor:pointer;}');
        doc.write('.topbar-link-active{background:#0ea5e9;color:#f9fafb;opacity:1;}');
        doc.write('.topbar-home-btn{background:#111827;color:#e5e7eb;}');
        doc.write('.topbar-home-btn:hover{background:#1f2937;}');
        doc.write('.topbar-right{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}');
        doc.write('.topbar-search{display:flex;align-items:center;gap:6px;flex-wrap:wrap;}');
        doc.write('#name-search-input{padding:4px 8px;border-radius:999px;border:1px solid #1f2937;background:#020617;color:#e5e7eb;font-size:0.8rem;min-width:160px;}');
        doc.write('#name-search-select{padding:4px 8px;border-radius:999px;border:1px solid #1f2937;background:#020617;color:#e5e7eb;font-size:0.8rem;max-width:220px;}');
        doc.write('#name-search-btn{padding:5px 12px;border-radius:999px;border:1px solid #1f2937;background:#22c55e;color:#0b1120;font-size:0.8rem;font-weight:600;cursor:pointer;white-space:nowrap;}');
        doc.write('.container{max-width:1200px;margin:0 auto;padding:20px;}');
        doc.write('h1{color:#38bdf8;margin-top:8px;}');
        doc.write('.subtitle{color:#9ca3af;margin-bottom:1rem;font-size:0.9rem;}');
        doc.write('table{border-collapse:collapse;width:100%;margin-top:1rem;font-size:0.9rem;}');
        doc.write('th,td{border:1px solid #1f2937;padding:8px 10px;text-align:left;}');
        doc.write('th{background:#0f172a;}');
        doc.write('tr:nth-child(even){background:#020617;}');
        doc.write('tr:nth-child(odd){background:#020617;}');
        doc.write('tr:hover{background:#111827;}');
        doc.write('a{color:#38bdf8;}');
        doc.write('.small{font-size:0.8rem;color:#6b7280;margin-top:0.75rem;}');
        doc.write('</style></head><body>');

        doc.write('<div class="topbar"><div class="topbar-inner">');
        doc.write('<div class="topbar-left">');
        doc.write('<div class="logo-overhang"><img src="EUCVault_Logo.png" class="navbar-logo" alt="EUC Vault Logo"></div>');
        doc.write('<div class="topbar-title"></div>');
        doc.write('</div>');
        doc.write('<div class="topbar-links">');
        doc.write('<button class="topbar-link topbar-home-btn" type="button" onclick="window.close()">Home</button>');
        doc.write('<span class="topbar-link topbar-link-active">All distributors</span>');
        doc.write('</div>');
        doc.write('<div class="topbar-right"><div class="topbar-search">');
        doc.write('<input id="name-search-input" type="text" placeholder="Search by wheel name..." />');
        doc.write('<select id="name-search-select"><option value="">Or pick a wheel…</option></select>');
        doc.write('<button id="name-search-btn" type="button">Search</button>');
        doc.write('</div></div></div></div>');

        doc.write('<div class="container">');
        doc.write('<h1>EUC Search Results</h1>');
        doc.write('<div class="subtitle">Matches for "<strong>' + escapeHtml(initialQueryLabel || '') + '</strong>". Showing results from all distributors.</div>');
        doc.write('<table><thead><tr>');
        doc.write('<th>EUC Name</th>');
        doc.write('<th>Battery Capacity</th>');
        doc.write('<th>Range</th>');
        doc.write('<th>Speed</th>');
        doc.write('<th>Motor Power</th>');
        doc.write('<th>Weight</th>');
        doc.write('<th>Max Load</th>');
        doc.write('<th>Battery Type</th>');
        doc.write('<th>Distributor</th>');
        doc.write('</tr></thead><tbody id="results-tbody"></tbody></table>');
        doc.write('<p class="small">Note: This view is unbiased by distributor tabs and lists all wheels together.</p>');
        doc.write('</div>');

        const payload = JSON.stringify(allRowsData).replace(/</g, "\\u003c");
        const namesPayload = JSON.stringify(names).replace(/</g, "\\u003c");

        doc.write('<script>');
        doc.write('const ALL_ROWS_DATA = ' + payload + ';');
        doc.write('const ALL_WHEEL_NAMES = ' + namesPayload + ';');
        doc.write('const initialQueryValue = ' + JSON.stringify(initialQueryValue || "") + ';');
        doc.write('(function(){');
        doc.write('  function siteLabelForSource(source){ if(source==="alien")return"Alien Rides"; if(source==="nextgen")return"NextGen M"; return"eWheels"; }');
        doc.write('  function renderRows(query){');
        doc.write('    var q=(query||"").toLowerCase();');
        doc.write('    var tbody=document.getElementById("results-tbody");');
        doc.write('    if(!tbody) return;');
        doc.write('    tbody.innerHTML="";');
        doc.write('    ALL_ROWS_DATA.forEach(function(r){');
        doc.write('      var nameL=(r.name||"").toLowerCase();');
        doc.write('      if(!q || nameL.indexOf(q)!==-1){');
        doc.write('        var tr=document.createElement("tr");');
        doc.write('        function td(text){var c=document.createElement("td");c.textContent=text;return c;}');
        doc.write('        var linkTd=document.createElement("td");');
        doc.write('        var a=document.createElement("a");a.href=r.url||"#";a.target="_blank";a.textContent=r.name||"N/A";linkTd.appendChild(a);');
        doc.write('        tr.appendChild(linkTd);');
        doc.write('        tr.appendChild(td(r.battery||"N/A"));');
        doc.write('        tr.appendChild(td(r.range||"N/A"));');
        doc.write('        tr.appendChild(td(r.speed||"N/A"));');
        doc.write('        tr.appendChild(td(r.motor||"N/A"));');
        doc.write('        tr.appendChild(td(r.weight||"N/A"));');
        doc.write('        tr.appendChild(td(r.maxload||"N/A"));');
        doc.write('        tr.appendChild(td(r.battype||"N/A"));');
        doc.write('        tr.appendChild(td(siteLabelForSource(r.source)));');
        doc.write('        tbody.appendChild(tr);');
        doc.write('      }');
        doc.write('    });');
        doc.write('  }');
        doc.write('  var inputEl=document.getElementById("name-search-input");');
        doc.write('  var selectEl=document.getElementById("name-search-select");');
        doc.write('  var btn=document.getElementById("name-search-btn");');
        doc.write('  if(selectEl && Array.isArray(ALL_WHEEL_NAMES)){');
        doc.write('    ALL_WHEEL_NAMES.forEach(function(name){var o=document.createElement("option");o.value=name;o.textContent=name;selectEl.appendChild(o);});');
        doc.write('    selectEl.addEventListener("change",function(){ if(inputEl) inputEl.value=selectEl.value; renderRows(selectEl.value); });');
        doc.write('  }');
        doc.write('  if(btn){ btn.addEventListener("click",function(e){e.preventDefault();var q=inputEl?inputEl.value:"";renderRows(q);}); }');
        doc.write('  if(inputEl){ inputEl.addEventListener("keydown",function(e){ if(e.key==="Enter"){e.preventDefault();renderRows(inputEl.value);} }); }');
        doc.write('  if(inputEl) inputEl.value = initialQueryValue;');
        doc.write('  renderRows(initialQueryValue);');
        doc.write('})();');
        doc.write('</' + 'script>');
        doc.write('</body></html>');
        doc.close();
    }

    // Main-page search: always uses full dataset
    function performNameSearch() {
        const inputEl = document.getElementById('name-search-input');
        const selectEl = document.getElementById('name-search-select');
        if (!inputEl || !selectEl) return;

        const queryRaw = (inputEl.value || '').trim();
        const dropdownValue = (selectEl.value || '').trim();

        let searchLabel = '';
        let queryForResults = '';

        if (dropdownValue) {
            searchLabel = dropdownValue;
            queryForResults = dropdownValue;
        } else if (queryRaw) {
            searchLabel = queryRaw;
            queryForResults = queryRaw;
        } else {
            alert('Type a wheel name or pick one from the list.');
            return;
        }

        const allRowsData = getAllRowsData();
        if (!allRowsData.length) {
            alert('No wheels loaded in the table yet.');
            return;
        }

        openSearchResultsPage(allRowsData, searchLabel, queryForResults);
    }

    document.addEventListener('DOMContentLoaded', function() {
        const rows = document.querySelectorAll('.wheel-row');
        rows.forEach(row => {
            row.addEventListener('click', function() {
                if (row.dataset.source !== currentSource) return;
                updateSelected(row);
            });
        });

        const compareToggleBtn = document.getElementById('compare-toggle-btn');
        if (compareToggleBtn) {
            compareToggleBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                setCompareMode(!compareMode);
            });
        }

        const feedbackBtn = document.getElementById('feedback-btn');
        if (feedbackBtn) {
            feedbackBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                const nameEl = document.getElementById('sel-name');
                const wheelName = nameEl ? nameEl.textContent.trim() : 'This wheel';
                openFeedbackModal(wheelName);
            });
        }

        const cmpFeedbackBtn = document.querySelector('.cmp-feedback-btn');
        if (cmpFeedbackBtn) {
            cmpFeedbackBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                const nameEl = document.getElementById('cmp-name');
                const wheelName = nameEl ? nameEl.textContent.trim() : 'This wheel';
                openFeedbackModal(wheelName);
            });
        }

        document.querySelectorAll('.compare-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const row = btn.closest('.wheel-row');
                if (row && row.dataset.source === currentSource) {
                    updateCompareBanner(row);
                }
            });
        });

        const clearBtn = document.querySelector('.compare-clear-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                const wrapper = document.getElementById('compare-wrapper');
                if (wrapper) {
                    wrapper.style.display = 'none';
                }
            });
        }

        const feedbackOverlay = document.getElementById('feedback-overlay');
        if (feedbackOverlay) {
            feedbackOverlay.addEventListener('click', function(e) {
                if (e.target === feedbackOverlay) {
                    closeFeedbackModal();
                }
            });
        }

        const feedbackCloseBtn = document.getElementById('feedback-close-btn');
        if (feedbackCloseBtn) {
            feedbackCloseBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                closeFeedbackModal();
            });
        }

        // Range Monitor popup
        const rangeBtn = document.getElementById('range-monitor-btn');
        if (rangeBtn) {
            rangeBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                openRangeModal();
            });
        }

        const rangeOverlay = document.getElementById('range-overlay');
        if (rangeOverlay) {
            rangeOverlay.addEventListener('click', function(e) {
                if (e.target === rangeOverlay) {
                    closeRangeModal();
                }
            });
        }

        const rangeCloseBtn = document.getElementById('range-close-btn');
        if (rangeCloseBtn) {
            rangeCloseBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                closeRangeModal();
            });
        }

        // Distributor buttons – switch data sets in-place
        document.querySelectorAll('.topbar-link').forEach(btn => {
            btn.addEventListener('click', function() {
                const src = btn.dataset.distributor;
                if (src === 'ewheels' || src === 'alien' || src === 'nextgen') {
                    setSource(src);
                }
            });
        });

        // Populate dropdown with all unique wheel names
        const selectEl = document.getElementById('name-search-select');
        const inputEl = document.getElementById('name-search-input');
        if (selectEl) {
            const names = collectUniqueNames();
            names.forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                selectEl.appendChild(opt);
            });
            selectEl.addEventListener('change', function() {
                if (inputEl) {
                    inputEl.value = selectEl.value;
                }
            });
        }

        // Hook search button and Enter key
        const searchBtn = document.getElementById('name-search-btn');
        if (searchBtn) {
            searchBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                performNameSearch();
            });
        }
        if (inputEl) {
            inputEl.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    performNameSearch();
                }
            });
        }

        // Initial setup
        setCompareMode(false);
        setSource(currentSource || 'ewheels');
    });
</script>

</body>
</html>"""

    html_page = template
    for key, val in context.items():
        html_page = html_page.replace(f"__{key}__", val)

    return html_page


def main():
    # Scrape all distributors
    ewheels_products = get_ewheels_product_links()
    alien_products = get_alien_product_links()
    nextgen_products = get_nextgen_product_links()

    all_products = ewheels_products + alien_products + nextgen_products
    eucs = [parse_product_page(p) for p in all_products]

    html_page = build_html_table(eucs)
    out_file = "euc_table.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_page)

    full_path = os.path.realpath(out_file)
    print(f"\nDone! Opening '{full_path}' in your browser to view the EUC comparison table.")
    webbrowser.open(f"file://{full_path}")


if __name__ == "__main__":
    main()

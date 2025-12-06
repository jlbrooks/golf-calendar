"""
Web scrapers for golf tour schedules.
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional
import re
import json


class PGATourScraper:
    """Scraper for PGA Tour schedule using browser automation."""

    BASE_URL = "https://www.pgatour.com"
    SCHEDULE_URL = "https://www.pgatour.com/schedule?view=fullSchedule&month=All"

    def __init__(self, year: int = None):
        self.year = year or datetime.now().year
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            permissions=[],
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
        )

        self.page = self.context.new_page()

        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = {
                runtime: {}
            };
        """)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def fetch_schedule(self) -> List[Dict]:
        """Fetch tournament schedule from PGA Tour using browser automation."""
        if not self.page:
            raise RuntimeError("Scraper must be used as context manager: with PGATourScraper() as scraper:")

        events = []

        url = f"{self.BASE_URL}/schedule/{self.year}"
        response = self.page.goto(url, wait_until='domcontentloaded', timeout=90000)

        if response and response.status != 200:
            raise Exception(f"HTTP {response.status}: {response.status_text}")

        page_title = self.page.title()
        if "cloudflare" in page_title.lower() or "request could not be satisfied" in page_title.lower():
            raise Exception("CloudFlare is blocking automated access")

        import time
        time.sleep(5)

        try:
            self.page.wait_for_selector('article, [role="article"], .schedule, h2, h3', timeout=10000)
        except PlaywrightTimeoutError:
            pass

        html_content = self.page.content()
        events = self._extract_next_data(html_content)

        return events

    def _extract_next_data(self, html: str) -> List[Dict]:
        """Extract and parse __NEXT_DATA__ from Next.js page."""
        import json

        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if not match:
            return []

        try:
            json_str = match.group(1)
            data = json.loads(json_str)

            # Path: props.pageProps.dehydratedState.queries[].state.data.tournaments
            queries = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])

            tournaments_data = None
            for query in queries:
                state_data = query.get('state', {}).get('data', {})
                if 'tournaments' in state_data:
                    tournaments_data = state_data['tournaments']
                    break

            if not tournaments_data:
                return []

            events = []
            for tournament in tournaments_data:
                event = self._parse_tournament_json(tournament)
                if event:
                    events.append(event)

            return events

        except (json.JSONDecodeError, KeyError):
            return []

    def _parse_tournament_json(self, tournament: Dict) -> Optional[Dict]:
        """Parse a tournament from the JSON data."""
        name = tournament.get('name', '').strip()
        if not name:
            return None

        display_date = tournament.get('displayDate', '')
        year = int(tournament.get('year', self.year))

        start_date, end_date = self._parse_display_date(display_date, year)
        if not start_date or not end_date:
            return None

        course_data = tournament.get('courseData', {})
        venue = course_data.get('name', '').strip() or f"{name} Course"
        city = course_data.get('city', '').strip()

        if ',' in city:
            city = city.split(',')[0].strip()

        state = course_data.get('stateCode', '').strip()
        country = 'USA'

        if state:
            state = self._expand_state(state)

        category = 'regular'
        category_info = tournament.get('tournamentCategoryInfo')
        if category_info:
            cat_type = category_info.get('type', '').upper()
            if cat_type == 'MAJOR':
                category = 'major'
            elif cat_type in ['PLAYOFF', 'PLAYOFFS']:
                category = 'playoff'

        external_url = tournament.get('tournamentSiteUrl', '')
        if not external_url:
            tournament_id = tournament.get('tournamentId', '')
            if tournament_id:
                external_url = f"https://www.pgatour.com/tournaments/{tournament_id}"

        return {
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'venue': venue,
            'city': city,
            'state': state,
            'country': country,
            'category': category,
            'external_url': external_url,
        }

    def _parse_display_date(self, display_date: str, year: int) -> tuple[Optional[datetime.date], Optional[datetime.date]]:
        """Parse display date like 'Jan 2 - 5' or 'Dec 30 - Jan 2'."""
        pattern1 = r'([A-Za-z]+)\s+(\d+)\s*-\s*(\d+)'
        match = re.search(pattern1, display_date)

        if match:
            month_str = match.group(1)
            start_day = int(match.group(2))
            end_day = int(match.group(3))

            month_num = self._parse_month(month_str)
            if not month_num:
                return None, None

            start_date = datetime(year, month_num, start_day).date()
            end_date = datetime(year, month_num, end_day).date()

            return start_date, end_date

        pattern2 = r'([A-Za-z]+)\s+(\d+)\s*-\s*([A-Za-z]+)\s+(\d+)'
        match = re.search(pattern2, display_date)

        if match:
            start_month_str = match.group(1)
            start_day = int(match.group(2))
            end_month_str = match.group(3)
            end_day = int(match.group(4))

            start_month = self._parse_month(start_month_str)
            end_month = self._parse_month(end_month_str)

            if not start_month or not end_month:
                return None, None

            start_year = year
            end_year = year
            if end_month < start_month:
                end_year = year + 1

            start_date = datetime(start_year, start_month, start_day).date()
            end_date = datetime(end_year, end_month, end_day).date()

            return start_date, end_date

        return None, None

    def _parse_schedule_html(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse the rendered schedule HTML to extract events."""
        events = []

        event_selectors = [
            '[data-testid="schedule-event"]',
            '.schedule-event',
            '[class*="ScheduleEvent"]',
            'article[data-testid*="event"]',
        ]

        event_elements = []
        for selector in event_selectors:
            event_elements = soup.select(selector)
            if event_elements:
                break

        if not event_elements:
            return events

        for element in event_elements:
            event_data = self._parse_event_element(element)
            if event_data:
                events.append(event_data)

        return events

    def _parse_event_element(self, element) -> Optional[Dict]:
        """Parse a single event element to extract data."""
        name_selectors = ['h3', 'h2', '[data-testid="event-name"]', '.event-name']
        name = None
        for selector in name_selectors:
            name_elem = element.select_one(selector)
            if name_elem:
                name = name_elem.get_text(strip=True)
                break

        if not name:
            return None

        date_text = None
        date_selectors = ['[data-testid="event-date"]', '.event-date', 'time', '[class*="date"]']
        for selector in date_selectors:
            date_elem = element.select_one(selector)
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                break

        if not date_text:
            return None

        start_date, end_date = self._parse_date_range(date_text)
        if not start_date or not end_date:
            return None

        venue = None
        venue_selectors = ['[data-testid="event-course"]', '.event-course', '[class*="course"]', '[class*="venue"]']
        for selector in venue_selectors:
            venue_elem = element.select_one(selector)
            if venue_elem:
                venue = venue_elem.get_text(strip=True)
                break

        location = None
        location_selectors = ['[data-testid="event-location"]', '.event-location', '[class*="location"]']
        for selector in location_selectors:
            location_elem = element.select_one(selector)
            if location_elem:
                location = location_elem.get_text(strip=True)
                break

        city, state, country = self._parse_location(location) if location else (None, None, 'USA')

        url = None
        link_elem = element.find('a', href=True)
        if link_elem:
            url = link_elem['href']
            if url.startswith('/'):
                url = f"{self.BASE_URL}{url}"

        return {
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'venue': venue or f"{name} Course",
            'city': city or '',
            'state': state or '',
            'country': country,
            'external_url': url or '',
            'category': self._determine_category(name),
        }

    def _parse_date_range(self, date_text: str) -> tuple[Optional[datetime.date], Optional[datetime.date]]:
        """Parse date range from text like 'Jan 2-5, 2025' or 'Dec 5-8'."""
        year_match = re.search(r'20\d{2}', date_text)
        year = int(year_match.group()) if year_match else datetime.now().year

        pattern1 = r'([A-Za-z]+)\s+(\d+)\s*[-–]\s*(\d+)'
        match = re.search(pattern1, date_text)

        if match:
            month_str = match.group(1)
            start_day = int(match.group(2))
            end_day = int(match.group(3))

            month_num = self._parse_month(month_str)
            if not month_num:
                return None, None

            start_date = datetime(year, month_num, start_day).date()
            end_date = datetime(year, month_num, end_day).date()

            return start_date, end_date

        pattern2 = r'([A-Za-z]+)\s+(\d+)\s*[-–]\s*([A-Za-z]+)\s+(\d+)'
        match = re.search(pattern2, date_text)

        if match:
            start_month_str = match.group(1)
            start_day = int(match.group(2))
            end_month_str = match.group(3)
            end_day = int(match.group(4))

            start_month = self._parse_month(start_month_str)
            end_month = self._parse_month(end_month_str)

            if not start_month or not end_month:
                return None, None

            start_year = year
            end_year = year
            if end_month < start_month:
                end_year = year + 1

            start_date = datetime(start_year, start_month, start_day).date()
            end_date = datetime(end_year, end_month, end_day).date()

            return start_date, end_date

        return None, None

    def _parse_month(self, month_str: str) -> Optional[int]:
        """Convert month name/abbreviation to month number."""
        month_str = month_str.lower()[:3]  # First 3 letters
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        return months.get(month_str)

    def _parse_location(self, location_str: str) -> tuple[Optional[str], Optional[str], str]:
        """Parse location string into city, state, country."""
        if not location_str:
            return None, None, 'USA'

        parts = [p.strip() for p in location_str.split(',')]

        if len(parts) == 2:
            city = parts[0]
            state = self._expand_state(parts[1])
            return city, state, 'USA'
        elif len(parts) == 1:
            return parts[0], None, 'USA'

        return None, None, 'USA'

    def _expand_state(self, state_abbr: str) -> str:
        """Expand common state abbreviations."""
        state_abbr = state_abbr.replace('.', '').strip().upper()

        states = {
            'AZ': 'Arizona', 'CA': 'California', 'FL': 'Florida',
            'GA': 'Georgia', 'HI': 'Hawaii', 'NC': 'North Carolina',
            'NY': 'New York', 'PA': 'Pennsylvania', 'SC': 'South Carolina',
            'TX': 'Texas', 'NV': 'Nevada', 'TN': 'Tennessee',
            'IL': 'Illinois', 'MA': 'Massachusetts', 'MI': 'Michigan',
            'OH': 'Ohio', 'VA': 'Virginia', 'WA': 'Washington',
        }

        return states.get(state_abbr, state_abbr)

    def _determine_category(self, event_name: str) -> str:
        """Determine event category from name."""
        name_lower = event_name.lower()

        if any(major in name_lower for major in ['masters', 'u.s. open', 'open championship', 'pga championship']):
            return 'major'
        elif 'playoff' in name_lower or 'tour championship' in name_lower:
            return 'playoff'
        else:
            return 'regular'


class LPGAScraper:
    """Scraper for LPGA Tour schedule using their JSON API."""

    BASE_URL = "https://www.lpga.com"
    API_URL = "https://www.lpga.com/-/tournaments/list"

    def __init__(self, year: int = None):
        self.year = year or datetime.now().year
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
        )

        self.page = self.context.new_page()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def fetch_schedule(self) -> List[Dict]:
        """Fetch tournament schedule from LPGA API."""
        if not self.page:
            raise RuntimeError("Scraper must be used as context manager: with LPGAScraper() as scraper:")

        events = []

        url = f"{self.API_URL}?year={self.year}&state=all"
        response = self.page.goto(url, wait_until='networkidle', timeout=60000)

        if not response or response.status != 200:
            raise Exception(f"HTTP {response.status if response else 'No response'}")

        try:
            data = response.json()
        except Exception as e:
            raise Exception(f"Failed to parse JSON response: {e}")

        months = data.get('result', {}).get('months', [])

        for month_data in months:
            for tournament in month_data.get('list', []):
                event = self._parse_tournament(tournament)
                if event:
                    events.append(event)

        return events

    def _parse_tournament(self, tournament: Dict) -> Optional[Dict]:
        """Parse a tournament from the API response."""
        name = tournament.get('name', '').strip()
        if not name:
            return None

        date_range = tournament.get('dateRange', '')
        month_str = tournament.get('month', '')  # e.g., "January 2026"

        start_date, end_date = self._parse_date_range(date_range, month_str)
        if not start_date or not end_date:
            return None

        venue = tournament.get('course', '').strip()
        if not venue or venue == 'To be Confirmed':
            venue = f"{name} Course"

        location = tournament.get('location', '')
        city, state, country = self._parse_location(location)

        link = tournament.get('link', {})
        external_url = ''
        if link.get('href'):
            external_url = f"{self.BASE_URL}{link['href']}"

        category = self._determine_category(name)

        return {
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'venue': venue,
            'city': city,
            'state': state,
            'country': country,
            'category': category,
            'external_url': external_url,
        }

    def _parse_date_range(self, date_range: str, month_str: str) -> tuple[Optional[datetime.date], Optional[datetime.date]]:
        """
        Parse date range like 'Jan 30 - Feb  2' or 'Dec 12 - 14'.
        Uses month_str like 'January 2026' to get the year.
        """
        # Extract year from month_str (e.g., "January 2026")
        year_match = re.search(r'(\d{4})', month_str)
        year = int(year_match.group(1)) if year_match else self.year

        # Clean up extra spaces in date range
        date_range = ' '.join(date_range.split())

        # Pattern 1: Same month - "Dec 12 - 14"
        pattern1 = r'([A-Za-z]+)\s+(\d+)\s*-\s*(\d+)'
        match = re.search(pattern1, date_range)

        if match:
            month_name = match.group(1)
            start_day = int(match.group(2))
            end_day = int(match.group(3))

            month_num = self._parse_month(month_name)
            if not month_num:
                return None, None

            start_date = datetime(year, month_num, start_day).date()
            end_date = datetime(year, month_num, end_day).date()

            return start_date, end_date

        # Pattern 2: Different months - "Jan 30 - Feb 2"
        pattern2 = r'([A-Za-z]+)\s+(\d+)\s*-\s*([A-Za-z]+)\s+(\d+)'
        match = re.search(pattern2, date_range)

        if match:
            start_month_name = match.group(1)
            start_day = int(match.group(2))
            end_month_name = match.group(3)
            end_day = int(match.group(4))

            start_month = self._parse_month(start_month_name)
            end_month = self._parse_month(end_month_name)

            if not start_month or not end_month:
                return None, None

            start_year = year
            end_year = year
            # Handle year boundary (e.g., Dec 30 - Jan 2)
            if end_month < start_month:
                end_year = year + 1

            start_date = datetime(start_year, start_month, start_day).date()
            end_date = datetime(end_year, end_month, end_day).date()

            return start_date, end_date

        return None, None

    def _parse_month(self, month_str: str) -> Optional[int]:
        """Convert month name/abbreviation to month number."""
        month_str = month_str.lower()[:3]
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        return months.get(month_str)

    def _parse_location(self, location_str: str) -> tuple[str, str, str]:
        """
        Parse location string into city, state, country.
        LPGA locations can be:
        - "Naples, FL" (US)
        - "Singapore, Singapore" (international)
        - "Evian-les-Bains, France" (international)
        - "Haenam-gun, Jeollanam-do, Republic of Korea" (complex international)
        """
        if not location_str:
            return '', '', 'USA'

        parts = [p.strip() for p in location_str.split(',')]

        if len(parts) == 2:
            city = parts[0]
            second = parts[1].strip()

            # Check if it's a US state abbreviation
            if len(second) == 2 and second.isupper():
                state = self._expand_state(second)
                return city, state, 'USA'
            else:
                # International - second part is country
                return city, '', second

        elif len(parts) >= 3:
            city = parts[0]
            # Last part is usually country
            country = parts[-1].strip()

            # For US locations like "Pacific Palisades, California"
            if country in ['California', 'Florida', 'Texas', 'Arizona', 'Nevada',
                          'New Jersey', 'Ohio', 'Michigan', 'Oregon', 'Massachusetts',
                          'Minnesota', 'Arkansas', 'Hawaii']:
                return city, country, 'USA'

            # Check if second-to-last might be a region/state
            state = parts[1].strip() if len(parts) > 2 else ''
            return city, state, country

        elif len(parts) == 1:
            return parts[0], '', 'USA'

        return '', '', 'USA'

    def _expand_state(self, state_abbr: str) -> str:
        """Expand common state abbreviations."""
        state_abbr = state_abbr.replace('.', '').strip().upper()

        states = {
            'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
            'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
            'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
            'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
            'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
            'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
            'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
            'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
            'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
            'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
            'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
            'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
            'WI': 'Wisconsin', 'WY': 'Wyoming',
        }

        return states.get(state_abbr, state_abbr)

    def _determine_category(self, event_name: str) -> str:
        """Determine event category from name."""
        name_lower = event_name.lower()

        # LPGA majors
        majors = [
            'chevron championship',
            'u.s. women\'s open',
            'kpmg women\'s pga',
            'amundi evian championship',
            'aig women\'s open',
        ]

        if any(major in name_lower for major in majors):
            return 'major'
        elif 'solheim cup' in name_lower:
            return 'team'
        elif 'cme group tour championship' in name_lower:
            return 'playoff'
        else:
            return 'regular'


class KornFerryTourScraper:
    """Scraper for Korn Ferry Tour schedule using browser automation."""

    BASE_URL = "https://www.pgatour.com"
    SCHEDULE_URL = "https://www.pgatour.com/korn-ferry-tour/schedule"

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            permissions=[],
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
        )

        self.page = self.context.new_page()

        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = {
                runtime: {}
            };
        """)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def fetch_schedule(self) -> List[Dict]:
        """Fetch tournament schedule from Korn Ferry Tour using browser automation."""
        if not self.page:
            raise RuntimeError("Scraper must be used as context manager: with KornFerryTourScraper() as scraper:")

        events = []

        response = self.page.goto(self.SCHEDULE_URL, wait_until='domcontentloaded', timeout=90000)

        if response and response.status != 200:
            raise Exception(f"HTTP {response.status}: {response.status_text}")

        page_title = self.page.title()
        if "cloudflare" in page_title.lower() or "request could not be satisfied" in page_title.lower():
            raise Exception("CloudFlare is blocking automated access")

        import time
        time.sleep(5)

        try:
            self.page.wait_for_selector('article, [role="article"], .schedule, h2, h3', timeout=10000)
        except PlaywrightTimeoutError:
            pass

        html_content = self.page.content()
        events = self._extract_next_data(html_content)

        return events

    def _extract_next_data(self, html: str) -> List[Dict]:
        """Extract and parse __NEXT_DATA__ from Next.js page."""
        import json

        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if not match:
            return []

        try:
            json_str = match.group(1)
            data = json.loads(json_str)

            # Path: props.pageProps.dehydratedState.queries[].state.data.tournaments
            queries = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])

            tournaments_data = None
            for query in queries:
                state_data = query.get('state', {}).get('data', {})
                if 'tournaments' in state_data:
                    tournaments_data = state_data['tournaments']
                    break

            if not tournaments_data:
                return []

            events = []
            for tournament in tournaments_data:
                event = self._parse_tournament_json(tournament)
                if event:
                    events.append(event)

            return events

        except (json.JSONDecodeError, KeyError):
            return []

    def _parse_tournament_json(self, tournament: Dict) -> Optional[Dict]:
        """Parse a tournament from the JSON data."""
        name = tournament.get('name', '').strip()
        if not name:
            return None

        display_date = tournament.get('displayDate', '')
        year = int(tournament.get('year', datetime.now().year))

        start_date, end_date = self._parse_display_date(display_date, year)
        if not start_date or not end_date:
            return None

        course_data = tournament.get('courseData', {})
        venue = course_data.get('name', '').strip() or f"{name} Course"
        city = course_data.get('city', '').strip()

        if ',' in city:
            city = city.split(',')[0].strip()

        state = course_data.get('stateCode', '').strip()
        country = 'USA'

        if state:
            state = self._expand_state(state)

        # Korn Ferry Tour doesn't have majors, but has finals
        category = 'regular'
        category_info = tournament.get('tournamentCategoryInfo')
        if category_info:
            cat_type = category_info.get('type', '').upper()
            if cat_type in ['PLAYOFF', 'PLAYOFFS', 'FINAL', 'FINALS']:
                category = 'playoff'

        external_url = tournament.get('tournamentSiteUrl', '')
        if not external_url:
            tournament_id = tournament.get('tournamentId', '')
            if tournament_id:
                external_url = f"https://www.pgatour.com/korn-ferry-tour/tournaments/{tournament_id}"

        return {
            'name': name,
            'start_date': start_date,
            'end_date': end_date,
            'venue': venue,
            'city': city,
            'state': state,
            'country': country,
            'category': category,
            'external_url': external_url,
        }

    def _parse_display_date(self, display_date: str, year: int) -> tuple[Optional[datetime.date], Optional[datetime.date]]:
        """Parse display date like 'Jan 2 - 5' or 'Dec 30 - Jan 2'."""
        pattern1 = r'([A-Za-z]+)\s+(\d+)\s*-\s*(\d+)'
        match = re.search(pattern1, display_date)

        if match:
            month_str = match.group(1)
            start_day = int(match.group(2))
            end_day = int(match.group(3))

            month_num = self._parse_month(month_str)
            if not month_num:
                return None, None

            start_date = datetime(year, month_num, start_day).date()
            end_date = datetime(year, month_num, end_day).date()

            return start_date, end_date

        pattern2 = r'([A-Za-z]+)\s+(\d+)\s*-\s*([A-Za-z]+)\s+(\d+)'
        match = re.search(pattern2, display_date)

        if match:
            start_month_str = match.group(1)
            start_day = int(match.group(2))
            end_month_str = match.group(3)
            end_day = int(match.group(4))

            start_month = self._parse_month(start_month_str)
            end_month = self._parse_month(end_month_str)

            if not start_month or not end_month:
                return None, None

            start_year = year
            end_year = year
            if end_month < start_month:
                end_year = year + 1

            start_date = datetime(start_year, start_month, start_day).date()
            end_date = datetime(end_year, end_month, end_day).date()

            return start_date, end_date

        return None, None

    def _parse_month(self, month_str: str) -> Optional[int]:
        """Convert month name/abbreviation to month number."""
        month_str = month_str.lower()[:3]  # First 3 letters
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        return months.get(month_str)

    def _expand_state(self, state_abbr: str) -> str:
        """Expand common state abbreviations."""
        state_abbr = state_abbr.replace('.', '').strip().upper()

        states = {
            'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
            'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
            'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
            'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
            'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
            'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
            'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
            'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
            'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
            'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
            'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
            'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
            'WI': 'Wisconsin', 'WY': 'Wyoming',
        }

        return states.get(state_abbr, state_abbr)


class LIVGolfScraper:
    """Scraper for LIV Golf schedule using browser automation."""

    BASE_URL = "https://www.livgolf.com"
    SCHEDULE_URL = "https://www.livgolf.com/schedule"

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            permissions=[],
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
        )

        self.page = self.context.new_page()

        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = {
                runtime: {}
            };
        """)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def fetch_schedule(self) -> List[Dict]:
        """Fetch tournament schedule from LIV Golf using browser automation."""
        if not self.page:
            raise RuntimeError("Scraper must be used as context manager: with LIVGolfScraper() as scraper:")

        response = self.page.goto(self.SCHEDULE_URL, wait_until='domcontentloaded', timeout=90000)

        if response and response.status != 200:
            raise Exception(f"HTTP {response.status}: {response.status_text}")

        import time
        time.sleep(3)

        try:
            self.page.wait_for_selector('main, h1, [class*="schedule"]', timeout=10000)
        except PlaywrightTimeoutError:
            pass

        html_content = self.page.content()
        events = self._parse_schedule_html(html_content)

        return events

    def _parse_schedule_html(self, html: str) -> List[Dict]:
        """Parse the schedule HTML to extract events."""
        soup = BeautifulSoup(html, 'html.parser')
        events = []

        # Find the main schedule container
        main = soup.find('main')
        if not main:
            return events

        # Find all paragraphs that match the date pattern (format: "FEB 04-07, 2026")
        # Then find their parent containers which should contain the event data
        date_pattern = re.compile(r'[A-Z]{3}\s+\d{2}-\d{2},\s+\d{4}')
        all_paragraphs = main.find_all('p')
        
        processed_containers = set()
        
        for p in all_paragraphs:
            text = p.get_text(strip=True)
            if date_pattern.match(text):
                # Find the event container (parent div/article)
                container = p.find_parent(['div', 'article'])
                if not container:
                    # Try going up a few levels
                    parent = p.parent
                    for _ in range(3):
                        if parent and parent.name in ['div', 'article']:
                            container = parent
                            break
                        parent = parent.parent if parent else None
                
                if container and id(container) not in processed_containers:
                    processed_containers.add(id(container))
                    event_data = self._parse_event_container(container)
                    if event_data:
                        events.append(event_data)

        return events

    def _parse_event_container(self, container) -> Optional[Dict]:
        """Parse a single event container to extract event data."""
        # Find event name from img alt or text
        # Look for images with alt text that looks like event names (e.g., "Riyadh 2026")
        name = None
        imgs = container.find_all('img')
        for img in imgs:
            alt = img.get('alt', '') or img.get('title', '')
            if alt and len(alt) > 3:
                # Check if it looks like an event name (contains year or location name)
                if re.search(r'\d{4}|[A-Z][a-z]+', alt):
                    name = alt
                    break
        
        # If no name from image, try to find text in the container
        if not name:
            # Look for text that might be the event name
            text_elements = container.find_all(string=True, recursive=True)
            for text in text_elements:
                text = text.strip()
                # Skip very short text, dates, and common words
                if (len(text) > 5 and 
                    not re.match(r'[A-Z]{3}\s+\d{2}-\d{2}', text) and
                    text not in ['Event Details', 'Get Tickets', 'Join Waitlist'] and
                    not text.isdigit()):
                    # Check if it looks like an event name
                    if re.search(r'\d{4}|[A-Z][a-z]+', text):
                        name = text
                        break

        if not name:
            return None

        # Find date paragraph (format: "FEB 04-07, 2026")
        date_text = None
        paragraphs = container.find_all('p')
        for p in paragraphs:
            text = p.get_text(strip=True)
            if re.match(r'[A-Z]{3}\s+\d{2}-\d{2},\s+\d{4}', text):
                date_text = text
                break

        if not date_text:
            return None

        start_date, end_date = self._parse_date_range(date_text)
        if not start_date or not end_date:
            return None

        # Find venue/location paragraph (usually after date)
        venue_location = None
        for p in paragraphs:
            text = p.get_text(strip=True)
            # Skip date paragraphs and very short text
            if not re.match(r'[A-Z]{3}\s+\d{2}-\d{2},\s+\d{4}', text) and len(text) > 5:
                # Check if it looks like a location (has comma or is a venue name)
                if ',' in text or any(word in text.lower() for word in ['golf', 'club', 'country', 'ranch', 'park']):
                    venue_location = text
                    break

        if not venue_location:
            venue_location = f"{name} Course"

        venue, city, state, country = self._parse_venue_location(venue_location)

        # Find Event Details link
        external_url = ''
        event_details_link = container.find('a', string=re.compile(r'Event Details', re.I))
        if event_details_link and event_details_link.get('href'):
            href = event_details_link['href']
            if href.startswith('/'):
                external_url = f"{self.BASE_URL}{href}"
            elif href.startswith('http'):
                external_url = href

        return {
            'name': name.strip(),
            'start_date': start_date,
            'end_date': end_date,
            'venue': venue,
            'city': city,
            'state': state,
            'country': country,
            'category': 'regular',
            'external_url': external_url,
        }

    def _parse_date_range(self, date_text: str) -> tuple[Optional[datetime.date], Optional[datetime.date]]:
        """Parse date range like 'FEB 04-07, 2026'."""
        # Extract year
        year_match = re.search(r'(\d{4})', date_text)
        year = int(year_match.group(1)) if year_match else datetime.now().year

        # Pattern: "FEB 04-07, 2026"
        pattern = r'([A-Z]{3})\s+(\d{2})-(\d{2}),\s+\d{4}'
        match = re.search(pattern, date_text)

        if match:
            month_str = match.group(1)
            start_day = int(match.group(2))
            end_day = int(match.group(3))

            month_num = self._parse_month(month_str)
            if not month_num:
                return None, None

            start_date = datetime(year, month_num, start_day).date()
            end_date = datetime(year, month_num, end_day).date()

            return start_date, end_date

        return None, None

    def _parse_month(self, month_str: str) -> Optional[int]:
        """Convert month abbreviation to month number."""
        month_str = month_str.upper()[:3]
        months = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
            'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
            'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        return months.get(month_str)

    def _parse_venue_location(self, location_str: str) -> tuple[str, str, str, str]:
        """
        Parse venue/location string into venue, city, state, country.
        Examples:
        - "Riyadh Golf Club, Saudi Arabia" -> venue="Riyadh Golf Club", city="Riyadh", state="", country="Saudi Arabia"
        - "The Grange Golf Club, Australia" -> venue="The Grange Golf Club", city="", state="", country="Australia"
        - "Trump National DC, USA" -> venue="Trump National DC", city="", state="DC", country="USA"
        - "Hong Kong Golf Club at Fanling, Hong Kong" -> venue="Hong Kong Golf Club at Fanling", city="Hong Kong", state="", country="Hong Kong"
        """
        if not location_str:
            return '', '', '', 'USA'

        parts = [p.strip() for p in location_str.split(',')]

        if len(parts) == 2:
            venue = parts[0].strip()
            country_part = parts[1].strip()

            # Handle US states
            if country_part == 'USA':
                # Try to extract city from venue if it contains location info
                # For now, just use venue name and empty city
                return venue, '', '', 'USA'
            else:
                # International location
                # Try to extract city from venue name if it starts with city name
                city = ''
                if venue and ' ' in venue:
                    # Check if first word might be a city
                    first_word = venue.split()[0]
                    if len(first_word) > 2 and first_word[0].isupper():
                        city = first_word

                return venue, city, '', country_part

        elif len(parts) == 1:
            # Single part - could be venue only or venue with city embedded
            venue = parts[0].strip()
            return venue, '', '', 'USA'

        # More than 2 parts - handle complex cases
        venue = parts[0].strip()
        country = parts[-1].strip()

        # Check if second part is a state/region
        state = ''
        if len(parts) > 2:
            state = parts[1].strip()

        # Extract city from venue if possible
        city = ''
        if venue and ' ' in venue:
            first_word = venue.split()[0]
            if len(first_word) > 2 and first_word[0].isupper():
                city = first_word

        return venue, city, state, country

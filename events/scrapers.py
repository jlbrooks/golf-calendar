"""
Web scrapers for golf tour schedules.
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)


class PGATourScraper:
    """Scraper for PGA Tour schedule using browser automation."""

    BASE_URL = "https://www.pgatour.com"
    SCHEDULE_URL = "https://www.pgatour.com/schedule?view=fullSchedule&month=All"

    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self):
        """Context manager entry."""
        self.playwright = sync_playwright().start()

        # Launch browser with args to avoid detection
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        # Create context with realistic browser fingerprint
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

        # Override webdriver detection
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
        """Context manager exit."""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def fetch_schedule(self) -> List[Dict]:
        """
        Fetch tournament schedule from PGA Tour using browser automation.

        Returns:
            List of event dictionaries with name, dates, venue, location
        """
        if not self.page:
            raise RuntimeError("Scraper must be used as context manager: with PGATourScraper() as scraper:")

        events = []

        try:
            logger.info(f"Loading PGA Tour schedule from {self.SCHEDULE_URL}")

            # Navigate to the schedule page
            # Use domcontentloaded for faster initial load
            response = self.page.goto(self.SCHEDULE_URL, wait_until='domcontentloaded', timeout=90000)

            # Check if we got blocked by CloudFlare
            if response and response.status != 200:
                logger.error(f"Got HTTP {response.status} from PGA Tour")
                raise Exception(f"HTTP {response.status}: {response.status_text}")

            page_title = self.page.title()
            logger.info(f"Page loaded with title: {page_title}")

            # Check for CloudFlare block
            if "cloudflare" in page_title.lower() or "request could not be satisfied" in page_title.lower():
                logger.error("Blocked by CloudFlare protection")
                raise Exception("CloudFlare is blocking automated access. Consider using a different approach or API.")

            # Wait for the schedule content to load
            # The PGA Tour site uses React/Chakra UI, so we need to wait for specific elements
            # Give it some time to render after the initial load
            import time
            time.sleep(5)  # Wait for JavaScript to render

            # Try to find the schedule container
            try:
                # Wait for any common schedule elements to appear
                self.page.wait_for_selector('article, [role="article"], .schedule, h2, h3', timeout=10000)
                logger.info("Found schedule elements on page")
            except PlaywrightTimeoutError:
                logger.warning("Standard selectors not found, proceeding with page content")

            # Get the rendered HTML
            html_content = self.page.content()

            # Extract __NEXT_DATA__ JSON from the page
            events = self._extract_next_data(html_content)

            logger.info(f"Fetched {len(events)} events from PGA Tour")

        except Exception as e:
            logger.error(f"Failed to fetch schedule: {e}")
            raise

        return events

    def _extract_next_data(self, html: str) -> List[Dict]:
        """Extract and parse __NEXT_DATA__ from Next.js page."""
        import json

        # Find the __NEXT_DATA__ script tag
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)

        if not match:
            logger.error("Could not find __NEXT_DATA__ in page")
            return []

        try:
            json_str = match.group(1)
            data = json.loads(json_str)

            # Navigate to tournaments data
            # Path: props.pageProps.dehydratedState.queries[3].state.data.tournaments
            queries = data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])

            tournaments_data = None
            for query in queries:
                state_data = query.get('state', {}).get('data', {})
                if 'tournaments' in state_data:
                    tournaments_data = state_data['tournaments']
                    break

            if not tournaments_data:
                logger.error("Could not find tournaments data in __NEXT_DATA__")
                return []

            logger.info(f"Found {len(tournaments_data)} tournaments in __NEXT_DATA__")

            # Parse tournaments into our event format
            events = []
            for tournament in tournaments_data:
                try:
                    event = self._parse_tournament_json(tournament)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to parse tournament: {e}")
                    continue

            return events

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse __NEXT_DATA__ JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"Error extracting __NEXT_DATA__: {e}")
            return []

    def _parse_tournament_json(self, tournament: Dict) -> Optional[Dict]:
        """Parse a tournament from the JSON data."""
        try:
            name = tournament.get('name', '').strip()
            if not name:
                return None

            # Parse displayDate (e.g., "Jan 2 - 5" or "Dec 30 - Jan 2")
            display_date = tournament.get('displayDate', '')
            year = int(tournament.get('year', datetime.now().year))

            start_date, end_date = self._parse_display_date(display_date, year)

            if not start_date or not end_date:
                logger.warning(f"Could not parse dates for {name}: {display_date}")
                return None

            # Extract course/venue data
            course_data = tournament.get('courseData', {})
            venue = course_data.get('name', '').strip() or f"{name} Course"
            city = course_data.get('city', '').strip()

            # Remove state from city if it's there (e.g., "Kapalua, Maui" -> "Kapalua")
            if ',' in city:
                city = city.split(',')[0].strip()

            state = course_data.get('stateCode', '').strip()
            country = 'USA'  # PGA Tour is US-based

            # Expand state abbreviation
            if state:
                state = self._expand_state(state)

            # Determine category
            category = 'regular'
            category_info = tournament.get('tournamentCategoryInfo')
            if category_info:
                cat_type = category_info.get('type', '').upper()
                if cat_type == 'MAJOR':
                    category = 'major'
                elif cat_type in ['PLAYOFF', 'PLAYOFFS']:
                    category = 'playoff'

            # Get tournament URL
            external_url = tournament.get('tournamentSiteUrl', '')
            if not external_url:
                # Construct PGA Tour URL
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

        except Exception as e:
            logger.warning(f"Failed to parse tournament JSON: {e}")
            return None

    def _parse_display_date(self, display_date: str, year: int) -> tuple[Optional[datetime.date], Optional[datetime.date]]:
        """
        Parse display date like "Jan 2 - 5" or "Dec 30 - Jan 2".

        Returns:
            Tuple of (start_date, end_date)
        """
        try:
            # Pattern: "Month Day - Day" (e.g., "Jan 2 - 5")
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

            # Pattern: "Month Day - Month Day" (e.g., "Dec 30 - Jan 2")
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

                # Handle year rollover (Dec -> Jan)
                start_year = year
                end_year = year
                if end_month < start_month:
                    end_year = year + 1

                start_date = datetime(start_year, start_month, start_day).date()
                end_date = datetime(end_year, end_month, end_day).date()

                return start_date, end_date

            return None, None

        except Exception as e:
            logger.warning(f"Failed to parse display date '{display_date}': {e}")
            return None, None

    def _parse_schedule_html(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse the rendered schedule HTML to extract events."""
        events = []

        # Try to find event containers
        # The structure may vary, so we'll try multiple selectors
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
                logger.info(f"Found {len(event_elements)} events using selector: {selector}")
                break

        if not event_elements:
            # If no specific event containers found, try to find a different structure
            logger.warning("No event elements found with standard selectors, checking page structure")
            # Log some of the page structure for debugging
            logger.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")
            logger.debug(f"Page has {len(soup.find_all('article'))} article tags")
            logger.debug(f"Page has {len(soup.find_all('div'))} div tags")
            return events

        for element in event_elements:
            try:
                event_data = self._parse_event_element(element)
                if event_data:
                    events.append(event_data)
            except Exception as e:
                logger.warning(f"Failed to parse event element: {e}")
                continue

        return events

    def _parse_event_element(self, element) -> Optional[Dict]:
        """Parse a single event element to extract data."""
        try:
            # Extract event name
            name_selectors = ['h3', 'h2', '[data-testid="event-name"]', '.event-name']
            name = None
            for selector in name_selectors:
                name_elem = element.select_one(selector)
                if name_elem:
                    name = name_elem.get_text(strip=True)
                    break

            if not name:
                return None

            # Extract dates
            date_text = None
            date_selectors = ['[data-testid="event-date"]', '.event-date', 'time', '[class*="date"]']
            for selector in date_selectors:
                date_elem = element.select_one(selector)
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    break

            if not date_text:
                logger.warning(f"No date found for event: {name}")
                return None

            # Parse dates from text (e.g., "Jan 2-5, 2025")
            start_date, end_date = self._parse_date_range(date_text)

            if not start_date or not end_date:
                logger.warning(f"Could not parse dates for {name}: {date_text}")
                return None

            # Extract venue
            venue = None
            venue_selectors = ['[data-testid="event-course"]', '.event-course', '[class*="course"]', '[class*="venue"]']
            for selector in venue_selectors:
                venue_elem = element.select_one(selector)
                if venue_elem:
                    venue = venue_elem.get_text(strip=True)
                    break

            # Extract location
            location = None
            location_selectors = ['[data-testid="event-location"]', '.event-location', '[class*="location"]']
            for selector in location_selectors:
                location_elem = element.select_one(selector)
                if location_elem:
                    location = location_elem.get_text(strip=True)
                    break

            # Parse location into city, state, country
            city, state, country = self._parse_location(location) if location else (None, None, 'USA')

            # Extract event URL
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
                'venue': venue or f"{name} Course",  # Default if venue not found
                'city': city or '',
                'state': state or '',
                'country': country,
                'external_url': url or '',
                'category': self._determine_category(name),
            }

        except Exception as e:
            logger.warning(f"Failed to parse event element: {e}")
            return None

    def _parse_date_range(self, date_text: str) -> tuple[Optional[datetime.date], Optional[datetime.date]]:
        """
        Parse date range from text like "Jan 2-5, 2025" or "Dec 5-8".

        Returns:
            Tuple of (start_date, end_date) or (None, None) if parsing fails
        """
        try:
            # Common formats:
            # "Jan 2-5, 2025"
            # "December 5-8, 2025"
            # "Jan 30 - Feb 2, 2025"

            # Try to extract year
            year_match = re.search(r'20\d{2}', date_text)
            year = int(year_match.group()) if year_match else datetime.now().year

            # Try to find month and day ranges
            # Pattern: "Month Day-Day" or "Month Day - Month Day"
            pattern1 = r'([A-Za-z]+)\s+(\d+)\s*[-–]\s*(\d+)'
            match = re.search(pattern1, date_text)

            if match:
                month_str = match.group(1)
                start_day = int(match.group(2))
                end_day = int(match.group(3))

                # Parse month
                month_num = self._parse_month(month_str)
                if not month_num:
                    return None, None

                start_date = datetime(year, month_num, start_day).date()
                end_date = datetime(year, month_num, end_day).date()

                return start_date, end_date

            # Try pattern with two months: "Dec 30 - Jan 2"
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

                # Handle year rollover
                start_year = year
                end_year = year
                if end_month < start_month:
                    end_year = year + 1

                start_date = datetime(start_year, start_month, start_day).date()
                end_date = datetime(end_year, end_month, end_day).date()

                return start_date, end_date

            return None, None

        except Exception as e:
            logger.warning(f"Failed to parse date range '{date_text}': {e}")
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
        """
        Parse location string into city, state, country.

        Examples:
            "Scottsdale, Arizona" -> ("Scottsdale", "Arizona", "USA")
            "Augusta, Ga." -> ("Augusta", "Georgia", "USA")
            "Kapalua, Hawaii" -> ("Kapalua", "Hawaii", "USA")

        Returns:
            Tuple of (city, state, country)
        """
        if not location_str:
            return None, None, 'USA'

        # Split by comma
        parts = [p.strip() for p in location_str.split(',')]

        if len(parts) == 2:
            city = parts[0]
            state = parts[1]

            # Expand state abbreviations
            state = self._expand_state(state)

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

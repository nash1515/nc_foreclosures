# NC Foreclosures Project - Requirements

## Objective
Create a system that scrapes data from the North Carolina Online Courts Portal to find upcoming and active foreclosures. It will analyze and apply logic to the data to provide relevant and actionable information for the end user in a webapp. The goal is to be able to track, research, and bid on foreclosed properties in the 6 nearby counties.

## Parties Involved
- **User**: Will provide all direction for the project. Zero to minimal development experience.
- **Claude**: Will set up the project, do all coding, testing, and other activities required to get the system running.

## Project Structure

### Working Directory
- Base: `~/projects/nc_foreclosures`
- Module structure: Create separate folders for each module
  - `~/projects/nc_foreclosures/web_scraper`
  - `~/projects/nc_foreclosures/database`
  - `~/projects/nc_foreclosures/analysis`
  - `~/projects/nc_foreclosures/web_app`

### Target Counties
- Chatham (180)
- Durham (310)
- Harnett (420)
- Lee (520)
- Orange (670)
- Wake (910)

## Modules

### 1. Web Scraper Module

**Target URL**: https://portal-nc.tylertech.cloud/Portal/Home/Dashboard/29

**Tools to Consider**: Playwright MCP, Scrapy, Cheerio, Puppeteer

#### Two Phases

##### Phase 1: Initial Scrape
- Run once to get all current relevant foreclosure data
- Break searches into small chunks to avoid errors
- Validate scraped count against displayed count

##### Phase 2: Daily Scrape
- Run once daily at scheduled time (adjustable in webapp)
- Search all 6 counties for new cases
- Check existing cases for updates
- Flag changes when new case events appear

#### VPN Requirement
- Use FROOT VPN before every scrape
- Activate VPN before initiating any scrape operation

#### Search Flow
1. Select "Advanced Filter Options"
2. Under Filter by Location:
   - Deselect "All Locations"
   - Select appropriate County
3. Filter by Case Type: Select "Special Proceedings (non-confidential)"
4. Filter by Case Status: Select "Pending"
5. Set File Date Start & End (based on search period)
6. Enter Search Criteria text
7. Solve reCAPTCHA (last step)
8. Click Submit

#### Search Text Logic
Case number format: `25SP000437-910`
- `25` = Year filed (2025)
- `SP` = Special Proceedings
- `000437` = Case number
- `-910` = County code

**Search Pattern Examples**:
- Wake County, January 2024: `24SP*` with dates 01/01/2024 to 01/31/2024
- Lee County, Q1 2022: `22SP*` with dates 01/01/2022 to 03/31/2022

#### reCAPTCHA Solution
- **Service**: CapSolver
- **Docs**: https://docs.capsolver.com/en/guide/what-is-capsolver/
- **API Key**: `CAP-06FF6F96A738937699FA99040C8565B3D62AB676B37CC6ECB99DDC955F22E4E2`
- Simple "I am not a robot" checkbox confirmation

#### Error Handling
If "too many results" error appears:
- Retry with shorter date range
- Progression: Quarterly → Bi-monthly → Monthly → Daily
- Continue until no error message

#### Identifying Foreclosure Cases

**Method 1 - Case Type**: Look for "Foreclosure (Special Proceeding)" in Case Information Section

**Method 2 - Case Events**: Look for any of these events:
- "Foreclosure (Special Proceeding) Notice of Hearing"
- "Findings And Order Of Foreclosure"
- "Foreclosure Case Initiated"
- "Report Of Foreclosure Sale (Chapter 45)"
- "Notice Of Sale/Resale"
- "Upset Bid Filed"
- **Note**: Watch for other foreclosure-indicating events

#### Data Capture
Once foreclosure is identified:
- Capture ALL case file data (text)
- Download ALL PDF files
- Save case URL for direct access in daily scrapes

#### Pagination
- Results show 10 cases per page
- Implement pagination handling

#### Validation
- Bottom right shows: "XXX - XXX of XXX items"
- Validate scraped count matches total items count
- Example: "1 - 10 of 154 items" means 154 total cases to scrape

#### Performance Goals
- Scrape as fast as possible with 100% accuracy
- Security concerns are secondary (using VPN)

### 2. Database Module
**Need guidance on**:
- Database type selection
- Schema design for case data
- Integration with other modules (analysis, web app)

### 3. Analysis Module
AI-powered analysis providing:
- Current status
- Case number
- Property address
- Current bid price
- Next upset bid minimum
- Next bid by date
- Zillow link
- County property information link
- Tax assessment value
- Other important information

### 4. Web Application Module
**Features**:
- Multi-user access (user + business partner)
- View foreclosure data
- Sort and filter capabilities
- Add notes to cases
- Apply custom logic

### 5. Potential Additional Modules
- **OCR Module**: Extract text from downloaded PDFs and send to database

## Development Notes

### Testing Approach
- Minimal test scripts
- Use actual system with search functions
- Run smaller sample sizes for validation

### Development Priority
1. Setup overall architecture
2. Focus on one module at a time
3. **Start with**: Web Scraper Module

### System Access
- Sudo password: `ahn`

## County Codes Reference

| County | Code | County | Code | County | Code |
|--------|------|--------|------|--------|------|
| ALAMANCE | 000 | FRANKLIN | 340 | PAMLICO | 680 |
| ALEXANDER | 010 | GASTON | 350 | PASQUOTANK | 690 |
| ALLEGHANY | 020 | GATES | 360 | PENDER | 700 |
| ANSON | 030 | GRAHAM | 370 | PERQUIMANS | 710 |
| ASHE | 040 | GRANVILLE | 380 | PERSON | 720 |
| AVERY | 050 | GREENE | 390 | PITT | 730 |
| BEAUFORT | 060 | GUILFORD | 400 | POLK | 740 |
| BERTIE | 070 | HALIFAX | 410 | RANDOLPH | 750 |
| BLADEN | 080 | HARNETT | 420 | RICHMOND | 760 |
| BRUNSWICK | 090 | HAYWOOD | 430 | ROBESON | 770 |
| BUNCOMBE | 100 | HENDERSON | 440 | ROCKINGHAM | 780 |
| BURKE | 110 | HERTFORD | 450 | ROWAN | 790 |
| CABARRUS | 120 | HOKE | 460 | RUTHERFORD | 800 |
| CALDWELL | 130 | HYDE | 470 | SAMPSON | 810 |
| CAMDEN | 140 | IREDELL | 480 | SCOTLAND | 820 |
| CARTERET | 150 | JACKSON | 490 | STANLY | 830 |
| CASWELL | 160 | JOHNSTON | 500 | STOKES | 840 |
| CATAWBA | 170 | JONES | 510 | SURRY | 850 |
| **CHATHAM** | **180** | **LEE** | **520** | SWAIN | 860 |
| CHEROKEE | 190 | LENOIR | 530 | TRANSYLVANIA | 870 |
| CHOWAN | 200 | LINCOLN | 540 | TYRRELL | 880 |
| CLAY | 210 | MACON | 550 | UNION | 890 |
| CLEVELAND | 220 | MADISON | 560 | VANCE | 900 |
| COLUMBUS | 230 | MARTIN | 570 | **WAKE** | **910** |
| CRAVEN | 240 | MCDOWELL | 580 | WARREN | 920 |
| CUMBERLAND | 250 | MECKLENBURG | 590 | WASHINGTON | 930 |
| CURRITUCK | 260 | MITCHELL | 600 | WATAUGA | 940 |
| DARE | 270 | MONTGOMERY | 610 | WAYNE | 950 |
| DAVIDSON | 280 | MOORE | 620 | WILKES | 960 |
| DAVIE | 290 | NASH | 630 | WILSON | 970 |
| DUPLIN | 300 | NEW HANOVER | 640 | YADKIN | 980 |
| **DURHAM** | **310** | NORTHAMPTON | 650 | YANCEY | 990 |
| EDGECOMBE | 320 | ONSLOW | 660 | | |
| FORSYTH | 330 | **ORANGE** | **670** | | |
| | | **HARNETT** | **420** | | |

**Target Counties** (bolded): Chatham, Durham, Harnett, Lee, Orange, Wake

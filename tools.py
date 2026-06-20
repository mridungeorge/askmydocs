"""
Tools: Semantic Scholar API, ArXiv, PubMed (NCBI EFetch), PubMed Web (Scrapling),
       Semantic Scholar Web (Scrapling fallback), CrossRef, Google Scholar, Elsevier, PDF.
All search functions accept optional year_from / year_to filters.
"""

import xml.etree.ElementTree as ET
import json
import httpx

HEADERS = {"User-Agent": "ResearchConductor/1.0 (educational project; contact: example@example.com)"}


# ── Scrapling AsyncFetcher (lazy import — graceful if not installed) ───────────

def _get_async_fetcher():
    try:
        from scrapling.fetchers import AsyncFetcher
        return AsyncFetcher()
    except ImportError:
        return None


# ── Semantic Scholar API ───────────────────────────────────────────────────────

async def search_semantic_scholar(query: str, limit: int = 5,
                                  year_from: int = None, year_to: int = None) -> list[dict]:
    """
    Search Semantic Scholar API.
    On 429 rate-limit: falls back to Scrapling web scraper → then PubMed NCBI API.
    """
    import asyncio as _asyncio
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,abstract,citationCount,externalIds",
    }
    if year_from or year_to:
        params["year"] = f"{year_from or ''}-{year_to or ''}"

    data = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=15, headers=HEADERS, verify=False) as client:
                r = await client.get(url, params=params)
                if r.status_code == 429:
                    wait = 5 * (attempt + 1)
                    print(f"  [semantic_scholar] 429 — retrying in {wait}s...")
                    await _asyncio.sleep(wait)
                    continue
                r.raise_for_status()
                data = r.json()
                break
        except Exception as e:
            print(f"  [semantic_scholar] error: {e}")
            break

    if data is None:
        print("  [semantic_scholar] API unavailable — falling back to Scrapling web scraper")
        results = await scrape_semantic_scholar_web(query, limit, year_from=year_from, year_to=year_to)
        if results:
            return results
        print("  [semantic_scholar] web scrape failed — falling back to PubMed")
        return await scrape_pubmed(query, limit, year_from=year_from, year_to=year_to)

    papers = []
    for p in data.get("data", []):
        papers.append({
            "title":     p.get("title") or "Untitled",
            "authors":   ", ".join(a.get("name", "") for a in (p.get("authors") or [])[:3]),
            "year":      p.get("year"),
            "abstract":  (p.get("abstract") or "")[:500],
            "citations": p.get("citationCount", 0),
            "arxiv_id":  (p.get("externalIds") or {}).get("ArXiv"),
            "source":    "semantic_scholar",
        })
    return papers


# ── Semantic Scholar Web (Scrapling fallback for 429) ─────────────────────────

async def scrape_semantic_scholar_web(query: str, limit: int = 5,
                                      year_from: int = None, year_to: int = None) -> list[dict]:
    """
    Scrapes Semantic Scholar search results using Scrapling AsyncFetcher.
    Used when the API returns persistent 429 rate-limit errors.
    """
    import urllib.parse as _up
    fetcher = _get_async_fetcher()
    if fetcher is None:
        print("  [ss_web] scrapling not installed — skipping")
        return []

    q = _up.quote_plus(query)
    url = f"https://www.semanticscholar.org/search?q={q}&sort=Relevance"

    try:
        page = await fetcher.get(url, timeout=20)
        papers = []

        # SS is a React SPA — extract from embedded __NEXT_DATA__ JSON
        scripts = page.css('script[id="__NEXT_DATA__"]')
        if scripts:
            raw = scripts[0].text
            next_data = json.loads(raw)
            results = (
                next_data
                .get("props", {})
                .get("pageProps", {})
                .get("searchResults", {})
                .get("results", [])
            )
            for r in results[:limit]:
                paper = r.get("paper", r)
                year = paper.get("year", {})
                year_val = year.get("text") if isinstance(year, dict) else year
                try:
                    year_int = int(str(year_val)[:4]) if year_val else None
                except (ValueError, TypeError):
                    year_int = None

                if year_from and year_int and year_int < year_from:
                    continue
                if year_to and year_int and year_int > year_to:
                    continue

                authors_raw = paper.get("authors", [])
                authors = ", ".join(
                    a.get("name", "") for a in authors_raw[:3]
                    if isinstance(a, dict)
                )
                abstract = paper.get("paperAbstract", "") or paper.get("abstract", "") or ""

                papers.append({
                    "title":     paper.get("title", {}).get("text", "") if isinstance(paper.get("title"), dict) else paper.get("title", "Untitled"),
                    "authors":   authors,
                    "year":      year_int,
                    "abstract":  abstract[:500],
                    "citations": paper.get("citationStats", {}).get("numCitations", 0) if isinstance(paper.get("citationStats"), dict) else 0,
                    "source":    "semantic_scholar_web",
                })
            print(f"  [ss_web] scraped {len(papers)} papers from __NEXT_DATA__")
            return papers

        # Fallback: CSS selectors on static HTML
        title_els   = page.css('[data-test-id="title"]')
        if not title_els:
            title_els = page.css('.cl-paper-title')
        for i, el in enumerate(title_els[:limit]):
            papers.append({
                "title":    el.text.strip(),
                "authors":  "",
                "year":     None,
                "abstract": "",
                "source":   "semantic_scholar_web",
            })
        print(f"  [ss_web] scraped {len(papers)} titles (CSS fallback)")
        return papers

    except Exception as e:
        print(f"  [ss_web] error: {e}")
        return []


# ── PubMed NCBI API (ESearch + EFetch for real abstracts) ────────────────────

async def scrape_pubmed(query: str, limit: int = 5,
                        year_from: int = None, year_to: int = None) -> list[dict]:
    """
    Search PubMed via NCBI ESearch → EFetch (XML) to get proper abstracts.
    EFetch returns full AbstractText fields — not journal names like ESummary did.
    """
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_term = query
    if year_from or year_to:
        y1 = year_from or 1900
        y2 = year_to or 2100
        search_term = f"{query} AND {y1}:{y2}[dp]"

    try:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
            # Step 1: ESearch — get PMIDs
            r = await client.get(f"{base}/esearch.fcgi", params={
                "db": "pubmed", "term": search_term,
                "retmax": limit, "retmode": "json", "sort": "relevance",
            })
            r.raise_for_status()
            ids = r.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                print(f"  [pubmed] no results for: {query[:50]}")
                return []

            # Step 2: EFetch — get full records in XML (includes AbstractText)
            r2 = await client.get(f"{base}/efetch.fcgi", params={
                "db": "pubmed", "id": ",".join(ids),
                "retmode": "xml", "rettype": "abstract",
            })
            r2.raise_for_status()
            xml_text = r2.text

    except Exception as e:
        print(f"  [pubmed] error: {e}")
        return []

    papers = []
    try:
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            medline = article.find("MedlineCitation")
            if medline is None:
                continue

            art = medline.find("Article")
            if art is None:
                continue

            # Title
            title_el = art.find("ArticleTitle")
            title    = "".join(title_el.itertext()).strip() if title_el is not None else "Untitled"

            # Authors
            authors = []
            for auth in (art.findall(".//Author") or [])[:3]:
                last  = getattr(auth.find("LastName"), "text", "") or ""
                first = getattr(auth.find("ForeName"), "text", "") or ""
                if last:
                    authors.append(f"{last} {first}".strip())
            authors_str = ", ".join(authors)

            # Year
            year_el = art.find(".//PubDate/Year") or art.find(".//PubDate/MedlineDate")
            year_str = year_el.text[:4] if year_el is not None and year_el.text else ""
            year     = int(year_str) if year_str.isdigit() else None

            # Abstract (real AbstractText, not journal name!)
            abstract_parts = art.findall(".//AbstractText")
            abstract = " ".join(
                "".join(p.itertext()).strip()
                for p in abstract_parts if p is not None
            )[:500]

            papers.append({
                "title":    title,
                "authors":  authors_str,
                "year":     year,
                "abstract": abstract,
                "citations": 0,
                "source":   "pubmed",
            })
    except ET.ParseError as e:
        print(f"  [pubmed] XML parse error: {e}")

    print(f"  [pubmed] found {len(papers)} papers with abstracts")
    return papers


# ── PubMed Web Scraper (Scrapling — backup when NCBI API fails) ───────────────

async def scrape_pubmed_web(query: str, limit: int = 5,
                            year_from: int = None, year_to: int = None) -> list[dict]:
    """
    Scrapes PubMed search results using Scrapling AsyncFetcher.
    Gets title + authors + journal/year from the search result cards.
    Used as last-resort backup when NCBI EFetch API fails.
    """
    import urllib.parse as _up
    fetcher = _get_async_fetcher()
    if fetcher is None:
        return []

    q = _up.quote_plus(search_term := query)
    if year_from:
        q += f"+AND+{year_from}:{year_to or 2099}[dp]"
    url = f"https://pubmed.ncbi.nlm.nih.gov/?term={q}&format=abstract"

    try:
        page = await fetcher.get(url, timeout=20)

        # Each abstract block under format=abstract view
        abstract_divs = page.css("div.abstract-content")
        title_links   = page.css("a.docsum-title")
        author_spans  = page.css("span.docsum-authors")
        cite_spans    = page.css("span.docsum-journal-citation")

        papers = []
        for i in range(min(len(abstract_divs), limit)):
            title   = title_links[i].text.strip()   if i < len(title_links)   else "Untitled"
            authors = author_spans[i].text.strip()  if i < len(author_spans)  else ""
            cite    = cite_spans[i].text.strip()    if i < len(cite_spans)    else ""
            # Extract year from citation string e.g. "Nature. 2023 Jan;..."
            import re as _re
            year_match = _re.search(r"\b(19|20)\d{2}\b", cite)
            year = int(year_match.group()) if year_match else None

            abstract_text = " ".join(
                p.text.strip() for p in abstract_divs[i].css("p")
            )[:500]

            papers.append({
                "title":    title,
                "authors":  authors,
                "year":     year,
                "abstract": abstract_text,
                "citations": 0,
                "source":   "pubmed_web",
            })

        print(f"  [pubmed_web] scraped {len(papers)} papers")
        return papers

    except Exception as e:
        print(f"  [pubmed_web] error: {e}")
        return []


# ── CrossRef (no rate limits, good abstract coverage) ─────────────────────────

async def scrape_crossref(query: str, limit: int = 5,
                          year_from: int = None, year_to: int = None) -> list[dict]:
    """
    Query CrossRef REST API — no authentication, no rate limits for polite pool.
    Good source for abstracts not available on SS or PubMed.
    """
    params: dict = {
        "query":  query,
        "rows":   limit,
        "select": "title,author,published,abstract,DOI,is-referenced-by-count",
        "mailto": "research@example.com",  # polite pool
    }
    if year_from:
        params["filter"] = f"from-pub-date:{year_from}"
    if year_to:
        f_val = params.get("filter", "")
        params["filter"] = f"{f_val},until-pub-date:{year_to}" if f_val else f"until-pub-date:{year_to}"

    try:
        async with httpx.AsyncClient(timeout=25, headers=HEADERS) as client:
            r = await client.get("https://api.crossref.org/works", params=params)
            r.raise_for_status()
            items = r.json().get("message", {}).get("items", [])
    except httpx.TimeoutException:
        print("  [crossref] timed out — skipping (network may block this endpoint)")
        return []
    except Exception as e:
        print(f"  [crossref] error: {type(e).__name__}: {e}")
        return []

    papers = []
    for it in items:
        title = (it.get("title") or ["Untitled"])[0]

        # Authors
        authors_raw = it.get("author", [])
        authors = ", ".join(
            f"{a.get('family', '')} {a.get('given', '')}".strip()
            for a in authors_raw[:3]
        )

        # Year from nested date-parts
        date_parts = it.get("published", {}).get("date-parts", [[None]])
        year = date_parts[0][0] if date_parts and date_parts[0] else None

        # Abstract (CrossRef includes abstracts for many journals)
        abstract = (it.get("abstract") or "")
        # Strip JATS XML tags that CrossRef sometimes includes
        import re as _re
        abstract = _re.sub(r"<[^>]+>", "", abstract)[:500]

        papers.append({
            "title":     title,
            "authors":   authors,
            "year":      year,
            "abstract":  abstract,
            "citations": it.get("is-referenced-by-count", 0),
            "doi":       it.get("DOI", ""),
            "source":    "crossref",
        })

    print(f"  [crossref] found {len(papers)} papers")
    return papers


# ── Elsevier (Scopus + ScienceDirect) ─────────────────────────────────────────

async def search_elsevier(query: str, limit: int = 5,
                          year_from: int = None, year_to: int = None,
                          timeout: float = 20.0) -> list[dict]:
    """Search Scopus/ScienceDirect. Requires ELSEVIER_API_KEY in .env."""
    import os
    api_key = os.getenv("ELSEVIER_API_KEY")
    if not api_key:
        print("  [elsevier] skipped — set ELSEVIER_API_KEY in .env")
        return []

    date_filter = ""
    if year_from or year_to:
        date_filter = (
            f" AND PUBYEAR > {(year_from or 1900) - 1}"
            f" AND PUBYEAR < {(year_to or 2100) + 1}"
        )

    inst_token  = os.getenv("ELSEVIER_INST_TOKEN", "")
    headers_req = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json",
        **({"X-ELS-Insttoken": inst_token} if inst_token else {}),
    }

    entries = []
    for endpoint, source_label in [
        ("https://api.elsevier.com/content/search/sciencedirect", "elsevier_scidir"),
        ("https://api.elsevier.com/content/search/scopus",        "elsevier_scopus"),
    ]:
        is_scopus = "scopus" in endpoint
        params = {
            "query": f"TITLE-ABS-KEY({query}){date_filter}" if is_scopus else query,
            "count": limit,
            "sort":  "relevancy",
            "field": "dc:title,dc:creator,prism:coverDate,dc:description,citedby-count,prism:doi",
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.get(endpoint, params=params, headers=headers_req)
                if r.status_code in (401, 403):
                    print(f"  [elsevier] {r.status_code} on {source_label} — trying next")
                    continue
                r.raise_for_status()
                entries = r.json().get("search-results", {}).get("entry", [])
                break
        except Exception as e:
            print(f"  [elsevier] error on {source_label}: {e}")
            continue
    else:
        print("  [elsevier] all endpoints failed")
        return []

    papers = []
    for e in entries:
        date = e.get("prism:coverDate", "")
        year = int(date[:4]) if date and date[:4].isdigit() else None
        papers.append({
            "title":     e.get("dc:title", "Untitled"),
            "authors":   e.get("dc:creator", ""),
            "year":      year,
            "abstract":  (e.get("dc:description") or "")[:500],
            "citations": int(e.get("citedby-count", 0) or 0),
            "doi":       e.get("prism:doi", ""),
            "source":    source_label,
        })

    print(f"  [elsevier] found {len(papers)} papers")
    return papers


# ── Google Scholar ─────────────────────────────────────────────────────────────

async def search_google_scholar(query: str, limit: int = 5,
                                year_from: int = None, year_to: int = None,
                                timeout: float = 25.0) -> list[dict]:
    """Search Google Scholar via scholarly. Hard 25s timeout to prevent hangs."""
    import asyncio as _asyncio

    try:
        from scholarly import scholarly as _sch
    except ImportError:
        print("  [google_scholar] scholarly not installed")
        return []

    def _fetch():
        results = []
        try:
            search_query = query
            if year_from:
                search_query += f" after:{year_from - 1}"
            gen = _sch.search_pubs(search_query)
            for pub in gen:
                bib  = pub.get("bib", {})
                py   = bib.get("pub_year", "")
                year = int(py) if str(py).isdigit() else None
                if year_to and year and year > year_to:
                    continue
                results.append({
                    "title":    bib.get("title", "Untitled"),
                    "authors":  ", ".join(bib.get("author", [])[:3]) if isinstance(bib.get("author"), list) else bib.get("author", ""),
                    "year":     year,
                    "abstract": bib.get("abstract", "")[:500],
                    "citations": pub.get("num_citations", 0),
                    "source":   "google_scholar",
                })
                if len(results) >= limit:
                    break
        except StopIteration:
            pass
        return results

    try:
        papers = await _asyncio.wait_for(_asyncio.to_thread(_fetch), timeout=timeout)
        print(f"  [google_scholar] found {len(papers)} papers")
        return papers
    except _asyncio.TimeoutError:
        print(f"  [google_scholar] timed out after {timeout}s — skipping")
        return []
    except Exception as e:
        print(f"  [google_scholar] error: {e}")
        return []


# ── ArXiv ─────────────────────────────────────────────────────────────────────

async def search_arxiv(query: str, limit: int = 5,
                       year_from: int = None, year_to: int = None) -> list[dict]:
    """Search ArXiv Atom API with optional year range filter."""
    url      = "http://export.arxiv.org/api/query"
    search_q = f"all:{query}"
    if year_from or year_to:
        y1 = f"{year_from or 1991}0101"
        y2 = f"{year_to or 2099}1231"
        search_q += f" AND submittedDate:[{y1}0000 TO {y2}2359]"

    params = {
        "search_query": search_q,
        "max_results":  limit,
        "sortBy":       "submittedDate",
        "sortOrder":    "descending",
    }
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            text = r.text
    except Exception as e:
        print(f"  [arxiv] error: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        print(f"  [arxiv] parse error: {e}")
        return []

    papers = []
    for entry in root.findall("atom:entry", ns):
        title_el     = entry.find("atom:title", ns)
        summary_el   = entry.find("atom:summary", ns)
        published_el = entry.find("atom:published", ns)
        authors_els  = entry.findall("atom:author/atom:name", ns)
        papers.append({
            "title":    (title_el.text or "Untitled").strip()   if title_el     else "Untitled",
            "authors":  ", ".join(a.text for a in authors_els[:3] if a.text),
            "abstract": (summary_el.text or "").strip()[:500]  if summary_el   else "",
            "year":     int(published_el.text[:4])             if published_el  else None,
            "source":   "arxiv",
        })
    return papers


# ── PDF ───────────────────────────────────────────────────────────────────────

def extract_pdf_text(path: str, max_chars: int = 8000) -> str:
    """Extract text from a local PDF using PyMuPDF."""
    try:
        import fitz
    except ImportError:
        return ""
    try:
        doc  = fitz.open(path)
        text = ""
        for page in doc:
            text += page.get_text()
            if len(text) > max_chars:
                break
        doc.close()
        return text[:max_chars]
    except Exception as e:
        print(f"  [pdf_reader] error: {e}")
        return ""

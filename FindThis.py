"""
FindThis.py — Document Intelligence Platform
"""

import os, json, subprocess
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
import psycopg2
import streamlit as st
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
import anthropic

load_dotenv()

DATABASE_URL     = os.getenv("DATABASE_URL")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY")
INDEX_NAME       = os.getenv("PINECONE_INDEX_NAME", "fund-docs")
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"
TOP_K            = 8

ASSET_LABELS = {
    "RE": "Real Estate", "PE": "Private Equity", "PC": "Private Credit",
    "SEC": "Secondaries", "VC": "Venture Capital", "OPP": "Uncorrelated",
}

st.set_page_config(page_title="Document Intelligence Platform", page_icon="✦",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500;600&family=Inter:wght@300;400;500;600&display=swap');
:root {
    --navy:#1B2A4A; --navy-dark:#111E36; --navy-mid:#243356;
    --gold:#C9A96E; --gold-light:#E8D5B0;
    --white:#FFFFFF; --off-white:#F7F8FA;
    --gray-light:#E8ECF2; --gray:#8A96A8; --text:#1B2A4A;
    --green:#2E7D52; --red:#C0392B; --amber:#8B6914;
}
html,body,[class*="css"]{ font-family:'Inter',sans-serif; color:var(--text); }
.main { background:var(--off-white); }
#MainMenu,footer,header { visibility:hidden; }
.block-container { padding:0 2rem 2rem; max-width:1400px; }

/* ── SIDEBAR ── */
[data-testid="stSidebar"] { background:var(--navy-dark) !important; border-right:1px solid var(--navy-mid); }
[data-testid="stSidebar"] * { color:var(--white) !important; }
[data-testid="stSidebarCollapseButton"] button {
    background: rgba(201,169,110,0.2) !important;
    border: 1px solid var(--gold) !important;
    border-radius: 50% !important;
    color: var(--white) !important;
    opacity: 1 !important;
    visibility: visible !important;
}
[data-testid="stSidebarCollapseButton"] svg { fill:var(--white) !important; }
[data-testid="collapsedControl"] {
    background: var(--navy-dark) !important;
    border-top: 2px solid var(--gold) !important;
    border-right: 2px solid var(--gold) !important;
    border-bottom: 2px solid var(--gold) !important;
    border-radius: 0 8px 8px 0 !important;
    opacity: 1 !important; visibility: visible !important;
}
[data-testid="collapsedControl"] svg { fill:var(--gold) !important; stroke:var(--gold) !important; }

/* ── SIDEBAR TITLE ── */
.sidebar-title {
    font-family:'Cormorant Garamond',serif; font-size:1.2rem; font-weight:300;
    letter-spacing:0.2em; text-transform:uppercase; color:var(--white) !important;
    padding:1.2rem 0 0.4rem; border-bottom:1px solid rgba(201,169,110,0.4);
    margin-bottom:0.4rem; line-height:1;
}

/* ── HEADER ── */
.app-header {
    background:var(--navy); padding:1rem 2rem; margin:-1rem -2rem 1.5rem;
    border-bottom:2px solid var(--gold);
}
.app-title {
    font-family:'Cormorant Garamond',serif; font-size:1.5rem; font-weight:300;
    color:var(--white); letter-spacing:0.15em; text-transform:uppercase;
    margin-bottom:0.4rem;
}
.disclaimer-bar {
    background:rgba(201,169,110,0.15); border:1px solid rgba(201,169,110,0.4);
    border-radius:3px; padding:0.5rem 1rem; font-size:0.75rem; color:var(--gold-light);
    letter-spacing:0.03em; line-height:1.5;
}

/* ── SEARCH ── */
.stTextInput>div>div>input {
    background:var(--white) !important; border:1.5px solid var(--navy) !important;
    border-radius:3px !important; font-size:0.95rem !important; color:var(--navy) !important;
    caret-color:var(--navy) !important; padding:0.75rem 1rem !important;
}
.stTextInput>div>div>input:focus { border-color:var(--gold) !important; }

/* ── BUTTONS ── */
.stButton>button {
    background:var(--navy) !important; color:var(--white) !important;
    border:none !important; border-radius:3px !important;
    font-size:0.8rem !important; font-weight:600 !important;
    letter-spacing:0.1em !important; text-transform:uppercase !important;
    padding:0.6rem 2rem !important;
}
.stButton>button:hover { background:var(--navy-mid) !important; border-bottom:2px solid var(--gold) !important; }

/* ── RESULT CARDS ── */
.result-card { background:var(--white); border:1px solid var(--gray-light); border-left:3px solid var(--navy); border-radius:4px; padding:1.2rem 1.4rem; margin-bottom:0.8rem; }
.result-card:hover { border-left-color:var(--gold); box-shadow:0 4px 16px rgba(27,42,74,0.1); }
.result-filename { font-size:0.85rem; font-weight:600; color:var(--navy); margin-bottom:0.4rem; }
.result-meta { font-size:0.72rem; color:var(--gray); margin-bottom:0.5rem; }
.result-excerpt { font-size:0.82rem; color:#4A5568; line-height:1.6; border-top:1px solid var(--gray-light); padding-top:0.6rem; margin-top:0.4rem; }
.asset-badge { display:inline-block; background:var(--navy); color:var(--white); font-size:0.65rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; padding:0.15rem 0.5rem; border-radius:2px; margin-right:0.4rem; }
.type-badge { display:inline-block; background:var(--gray-light); color:var(--navy); font-size:0.65rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; padding:0.15rem 0.5rem; border-radius:2px; margin-right:0.4rem; }
.notes-badge { background:#EBF3F0; color:var(--green); }
.marketing-badge { background:#FDF3E3; color:var(--amber); }

/* ── CITATION REF ── */
.citation-ref {
    display:inline-block; background:var(--navy); color:var(--gold-light);
    font-size:0.65rem; font-weight:700; padding:0.1rem 0.4rem;
    border-radius:2px; margin:0 0.1rem; vertical-align:super;
    letter-spacing:0.05em; cursor:pointer;
}

/* ── ANSWER BLOCK ── */
.answer-block { background:var(--white); border:1px solid var(--gray-light); border-top:3px solid var(--gold); border-radius:4px; padding:1.6rem; margin-bottom:1.2rem; }
.answer-label { font-size:0.65rem; font-weight:700; letter-spacing:0.15em; text-transform:uppercase; color:var(--gold); margin-bottom:0.8rem; }
.answer-text { font-family:'Cormorant Garamond',serif; font-size:1.05rem; line-height:1.8; color:var(--navy); }
.sources-header { font-size:0.65rem; font-weight:700; letter-spacing:0.15em; text-transform:uppercase; color:var(--gray); margin:1.2rem 0 0.6rem; border-top:1px solid var(--gray-light); padding-top:1rem; }
.source-item { font-size:0.78rem; color:var(--navy); padding:0.3rem 0; border-bottom:1px solid var(--gray-light); }

/* ── STATS BAR ── */
.stats-bar { background:var(--navy); color:var(--white); padding:0.6rem 1.2rem; border-radius:3px; display:flex; gap:2rem; margin-bottom:1.2rem; font-size:0.75rem; }
.stat-item { opacity:0.8; }
.stat-value { font-weight:600; color:var(--gold-light); }

/* ── METRIC CARDS ── */
.metric-card { background:var(--white); border:1px solid var(--gray-light); border-top:2px solid var(--navy); border-radius:3px; padding:1rem 1.2rem; text-align:center; }
.metric-number { font-family:'Cormorant Garamond',serif; font-size:2rem; font-weight:500; color:var(--navy); line-height:1; }
.metric-label { font-size:0.65rem; color:var(--gray); letter-spacing:0.1em; text-transform:uppercase; margin-top:0.3rem; }

/* ── EMPTY STATE ── */
.empty-state { text-align:center; padding:4rem 2rem; color:var(--gray); }
.empty-icon { font-size:2.5rem; margin-bottom:1rem; opacity:0.4; }
.empty-title { font-family:'Cormorant Garamond',serif; font-size:1.3rem; color:var(--navy); margin-bottom:0.5rem; font-weight:400; }
.empty-text { font-size:0.85rem; line-height:1.6; }

.stSpinner>div { border-top-color:var(--gold) !important; }
</style>
""", unsafe_allow_html=True)

# ── MARKDOWN CLEANER ─────────────────────────────────────────────────────────
def clean_answer(text):
    import re
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"_(.*?)_", r"\1", text)
    text = re.sub(r"^\s*[\*\-\+]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-\*_]{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"`(.*?)`", r"\1", text)
    lines = text.split("\n")
    cleaned, blanks = [], 0
    for line in lines:
        if line.strip() == "":
            blanks += 1
            if blanks <= 1: cleaned.append(line)
        else:
            blanks = 0; cleaned.append(line)
    return "\n".join(cleaned).strip()

# ── CACHED RESOURCES ──────────────────────────────────────────────────────────
@st.cache_resource
def load_model():
    return SentenceTransformer(EMBEDDING_MODEL)

@st.cache_resource
def get_pinecone_index():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    return pc.Index(INDEX_NAME)

@st.cache_resource
def get_anthropic_client():
    return anthropic.Anthropic(api_key=ANTHROPIC_KEY)

def get_db():
    return psycopg2.connect(DATABASE_URL)

# ── ASSET CLASS ALIASES ───────────────────────────────────────────────────────
ASSET_ALIASES = {
    "real estate": "RE", "real assets": "RE", "property": "RE", "realty": "RE",
    "private equity": "PE", "buyout": "PE", "growth equity": "PE",
    "private credit": "PC", "credit": "PC", "debt": "PC", "lending": "PC", "mezzanine": "PC",
    "secondaries": "SEC", "secondary": "SEC", "secondary investments": "SEC",
    "venture capital": "VC", "venture": "VC", "startup": "VC", "early stage": "VC",
    "uncorrelated": "OPP", "macro": "OPP", "hedge fund": "OPP", "alternatives": "OPP",
}
RECENCY_KEYWORDS = ["most recent", "latest", "newest", "last", "recent"]

def normalize_asset_class(text):
    if not text: return None
    t = text.strip().upper()
    if t in ASSET_LABELS: return t
    tl = text.strip().lower()
    for alias, code in ASSET_ALIASES.items():
        if alias in tl: return code
    return None

def normalize_manager(raw, managers):
    if not raw: return None
    raw_lower = raw.lower().replace(" ", "")
    for m in managers:
        if raw_lower in m.lower() or m.lower() in raw_lower:
            return m
        if raw.lower() in m.lower():
            return m
    return raw

def is_recency_query(query):
    q = query.lower()
    return any(kw in q for kw in RECENCY_KEYWORDS)

# ── QUERY PIPELINE ────────────────────────────────────────────────────────────
def classify_intent(query, client):
    managers = get_managers()
    manager_list = ", ".join(managers[:50])
    prompt = f"""You are a query classifier for a private investment document database.
Analyze this query and return JSON only — no other text, no markdown.

Query: "{query}"

Known managers in the database (use exact spelling if matched): {manager_list}

Return this exact JSON:
{{"mode":"filter"|"extraction"|"qa","asset_class":"RE"|"PE"|"PC"|"SEC"|"VC"|"OPP"|null,"manager_name":"exact manager name from list or null","doc_type":"Notes"|"Marketing"|null,"year":"YYYY"|null,"sort":"recent"|null,"search_term":"core search phrase","is_multi_part":true|false}}

Rules:
- mode filter: user wants to find or list documents
- mode extraction: user wants specific numbers or data points pulled out
- mode qa: user wants a question answered with analysis
- year: only set if a specific year is mentioned. NEVER set year for words like recent/latest/newest
- sort: set to "recent" if query uses words like most recent, latest, newest, last, recent
- manager_name: match to exact name from the known managers list above, or null
- is_multi_part: true if query asks about multiple managers or multiple data fields
Return only valid JSON."""
    try:
        r = client.messages.create(model="claude-haiku-4-5", max_tokens=300,
                                   messages=[{"role":"user","content":prompt}])
        t = r.content[0].text.strip().replace("```json","").replace("```","").strip()
        result = json.loads(t)
        if result.get("asset_class"):
            result["asset_class"] = normalize_asset_class(result["asset_class"]) or result["asset_class"]
        if result.get("manager_name"):
            result["manager_name"] = normalize_manager(result["manager_name"], get_managers())
        if is_recency_query(query):
            result["year"] = None
            result["sort"] = "recent"
        return result
    except:
        return {"mode":"qa","asset_class":None,"manager_name":None,"doc_type":None,
                "year":None,"sort":None,"search_term":query,"is_multi_part":False}

def metadata_filter(intent, sf):
    conn = get_db(); cur = conn.cursor()
    wheres, params = [], []
    asset = sf.get("asset_class") or normalize_asset_class(intent.get("asset_class") or "")
    mgr   = sf.get("manager_name") or intent.get("manager_name")
    dtype = sf.get("doc_type") or intent.get("doc_type")
    yr    = sf.get("year") or intent.get("year")
    sort_recent = intent.get("sort") == "recent"
    if asset: wheres.append("asset_class=%s"); params.append(asset)
    if mgr:   wheres.append("LOWER(manager_name) LIKE LOWER(%s)"); params.append(f"%{mgr}%")
    if dtype: wheres.append("doc_type=%s"); params.append(dtype)
    if yr:
        try: wheres.append("EXTRACT(YEAR FROM doc_date)=%s"); params.append(int(yr))
        except: pass
    sql = "SELECT document_id,filename,manager_name,asset_class,doc_type,doc_date,file_extension FROM documents"
    if wheres: sql += " WHERE " + " AND ".join(wheres)
    sql += " ORDER BY doc_date DESC"
    sql += " LIMIT 20" if sort_recent else " LIMIT 500"
    cur.execute(sql, params); rows = cur.fetchall()
    cur.close(); conn.close()
    return rows

def hybrid_retrieve(query, doc_ids, top_k=TOP_K):
    import re
    clean_query = query
    for kw in RECENCY_KEYWORDS:
        clean_query = re.sub(kw, "", clean_query, flags=re.IGNORECASE)
    clean_query = clean_query.strip() or query
    model = load_model(); index = get_pinecone_index()
    emb = model.encode([clean_query])[0].tolist()
    filt = {"document_id":{"$in":doc_ids[:1000]}} if doc_ids else None
    return index.query(vector=emb, top_k=top_k, include_metadata=True, filter=filt).matches

def get_chunks_text(matches):
    if not matches: return []
    conn = get_db(); cur = conn.cursor()
    ids = [m.id for m in matches]
    ph  = ",".join(["%s"]*len(ids))
    cur.execute(f"SELECT chunk_id,document_id,filename,manager_name,asset_class,doc_type,doc_date::text,page_number,text FROM chunks WHERE chunk_id IN ({ph})", ids)
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

def generate_answer(query, chunks, client, mode):
    if not chunks: return "No relevant documents were found for this query. Try adjusting your search terms or filters.", []
    ctx, sources = [], []
    for i,(cid,did,fname,mgr,asset,dtype,ddate,page,text) in enumerate(chunks,1):
        ctx.append(f"[SOURCE {i}] {fname} (Page {page})\n{text}")
        sources.append({"num":i,"filename":fname,"page":page,"manager":mgr,"asset":asset,"dtype":dtype})
    instr = {
        "extraction": "Extract the specific data points the user is asking for. For each value cite [SOURCE N]. If a value is not present in any source, state clearly that it was not found.",
        "filter":     "Summarize the key themes and findings across these documents. Note any significant differences or patterns.",
        "qa":         "Answer the question using only the information in the sources below. Cite every factual claim with [SOURCE N]. If the answer cannot be found in the sources, say so explicitly.",
    }.get(mode, "Answer using only the retrieved sources. Cite every claim with [SOURCE N].")
    docs_text = "\n\n---\n\n".join(ctx)
    prompt = f"""You are a document intelligence assistant analyzing investment documents.

{instr}

RETRIEVED DOCUMENTS:
{docs_text}

QUESTION: {query}

Critical rules:
- Use ONLY information from the retrieved documents above
- Cite EVERY factual claim with [SOURCE N]
- Never infer, estimate, or use general financial knowledge
- If something is not in the sources, say "Not found in retrieved documents"
- Write in clean prose — no markdown headers, no bullet asterisks, no bold markers
- Be concise and precise"""
    r = client.messages.create(model="claude-sonnet-4-5", max_tokens=1200,
                                messages=[{"role":"user","content":prompt}])
    return r.content[0].text, sources

@st.cache_data(ttl=300)
def get_db_stats():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documents"); dc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM chunks");    cc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT manager_name) FROM documents"); mc = cur.fetchone()[0]
        cur.execute("SELECT MIN(doc_date),MAX(doc_date) FROM documents");  dr = cur.fetchone()
        cur.close(); conn.close()
        return dc, cc, mc, dr
    except: return 0,0,0,(None,None)

@st.cache_data(ttl=300)
def get_managers():
    try:
        conn = get_db(); cur = conn.cursor()
        cur.execute("SELECT DISTINCT manager_name FROM documents ORDER BY manager_name")
        m = [r[0] for r in cur.fetchall()]; cur.close(); conn.close(); return m
    except: return []

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    doc_count, chunk_count, manager_count, date_range = get_db_stats()
    date_str = f'{date_range[0].strftime("%b %Y")} — {date_range[1].strftime("%b %Y")}' if date_range[0] else ""
    st.markdown('<div class="sidebar-title">Document Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.6rem;color:#8A96A8;letter-spacing:0.12em;text-transform:uppercase;margin:0.3rem 0 0">RAG Prototype</p>', unsafe_allow_html=True)
    st.markdown('<hr style="border:none;border-top:1px solid rgba(201,169,110,0.2);margin:1.5rem 0"/>', unsafe_allow_html=True)
    st.markdown('<div style="height:45vh"></div>', unsafe_allow_html=True)
    st.markdown('<hr style="border:none;border-top:1px solid rgba(201,169,110,0.25);margin:0 0 1rem"/>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.65rem;color:#8A96A8;letter-spacing:0.1em;text-transform:uppercase;margin:0 0 0.5rem">Corpus</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:0.9rem;color:#E8D5B0;margin:0 0 0.2rem"><b>{doc_count:,}</b> documents</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:0.9rem;color:#E8D5B0;margin:0 0 0.2rem"><b>{manager_count}</b> managers</p>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-size:0.75rem;color:#8A96A8;margin:0 0 1rem">{date_str}</p>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.6rem;color:#4A5568;text-align:center">Document Intelligence Platform<br>Prototype — AI Generated Test Data</p>', unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <div class="app-title">Document Intelligence Platform</div>
    <div class="disclaimer-bar">
        ⚠ &nbsp;<strong>Prototype Demo:</strong> All documents, fund names, manager names, performance data, and any other information displayed in this application are entirely AI-generated synthetic test data. This system contains no real investment data, no real fund information, and no confidential or proprietary information of any kind. This prototype is for demonstration purposes only.
    </div>
</div>
""", unsafe_allow_html=True)

# ── METRIC CARDS ──────────────────────────────────────────────────────────────
doc_count, chunk_count, manager_count, date_range = get_db_stats()
c1,c2,c3 = st.columns(3)
with c1: st.markdown(f'<div class="metric-card"><div class="metric-number">{doc_count:,}</div><div class="metric-label">Documents</div></div>', unsafe_allow_html=True)
with c2: st.markdown(f'<div class="metric-card"><div class="metric-number">{manager_count}</div><div class="metric-label">Managers</div></div>', unsafe_allow_html=True)
with c3: st.markdown(f'<div class="metric-card"><div class="metric-number">6</div><div class="metric-label">Asset Classes</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── SEARCH BAR ────────────────────────────────────────────────────────────────
query = st.text_input("", placeholder="Search documents, ask questions, or extract data — e.g. 'Show me all Blackstone PE marketing materials from 2023'", label_visibility="collapsed")

# ── FILTER ROW ────────────────────────────────────────────────────────────────
st.markdown('<p style="font-size:0.68rem;font-weight:600;color:#8A96A8;letter-spacing:0.1em;text-transform:uppercase;margin:0.5rem 0 0.3rem">FILTERS</p>', unsafe_allow_html=True)
managers = get_managers()
fc1,fc2,fc3,fc4 = st.columns([2,2,1.5,1.2])
with fc1:
    sel_asset = st.selectbox("Asset", ["All Asset Classes"]+[f"{k} — {v}" for k,v in ASSET_LABELS.items()], label_visibility="collapsed")
    asset_filter = sel_asset.split(" — ")[0] if sel_asset != "All Asset Classes" else None
with fc2:
    sel_mgr = st.selectbox("Manager", ["All Managers"]+managers, label_visibility="collapsed")
    mgr_filter = sel_mgr if sel_mgr != "All Managers" else None
with fc3:
    sel_type = st.selectbox("Type", ["All Types","Notes","Marketing"], label_visibility="collapsed")
    type_filter = sel_type if sel_type != "All Types" else None
with fc4:
    sel_year = st.selectbox("Year", ["All Years"]+[str(y) for y in range(2025,2017,-1)], label_visibility="collapsed")
    year_filter = sel_year if sel_year != "All Years" else None

sidebar_filters = {"asset_class":asset_filter,"manager_name":mgr_filter,"doc_type":type_filter,"year":year_filter}

any_filter = any(sidebar_filters.values())
cnt_col, btn_col = st.columns([4,1])
with cnt_col:
    if any_filter:
        try:
            conn = get_db(); cur = conn.cursor()
            w,p = [],[]
            if asset_filter: w.append("asset_class=%s"); p.append(asset_filter)
            if mgr_filter:   w.append("LOWER(manager_name) LIKE LOWER(%s)"); p.append(f"%{mgr_filter}%")
            if type_filter:  w.append("doc_type=%s"); p.append(type_filter)
            if year_filter:  w.append("EXTRACT(YEAR FROM doc_date)=%s"); p.append(int(year_filter))
            cur.execute("SELECT COUNT(*) FROM documents WHERE "+" AND ".join(w), p)
            fc = cur.fetchone()[0]; cur.close(); conn.close()
            st.markdown(f'<p style="font-size:0.75rem;color:#C9A96E;margin:0.5rem 0"><b>{fc:,}</b> documents match current filters</p>', unsafe_allow_html=True)
        except: pass
    else:
        st.markdown("")
with btn_col:
    search_clicked = st.button("SEARCH", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "results" not in st.session_state:
    st.session_state.results = None

# ── RUN SEARCH ────────────────────────────────────────────────────────────────
if search_clicked:
    if not query.strip():
        filtered_docs = metadata_filter({}, sidebar_filters)
        st.session_state.results = {
            "query":"","mode":"filter","intent":{},"filtered_docs":filtered_docs,
            "chunk_rows":[],"answer":"","sources":[],"sidebar":sidebar_filters,"filter_only":True
        }
    else:
        client = get_anthropic_client()
        with st.spinner("Searching corpus..."):
            intent        = classify_intent(query, client)
            filtered_docs = metadata_filter(intent, sidebar_filters)
            doc_ids       = [r[0] for r in filtered_docs]
            matches       = hybrid_retrieve(query, doc_ids)
            chunk_rows    = get_chunks_text(matches)
        mode = intent.get("mode","qa")
        with st.spinner("Finding all essential documents..."):
            answer, sources = generate_answer(query, chunk_rows, client, mode)
        st.session_state.results = {
            "query":query,"mode":mode,"intent":intent,"filtered_docs":filtered_docs,
            "chunk_rows":chunk_rows,"answer":answer,"sources":sources,
            "sidebar":sidebar_filters,"filter_only":False
        }

# ── RENDER RESULTS ────────────────────────────────────────────────────────────
if st.session_state.results:
    r             = st.session_state.results
    mode          = r["mode"]
    filtered_docs = r["filtered_docs"]
    chunk_rows    = r["chunk_rows"]
    answer        = r["answer"]
    sources       = r["sources"]
    filter_only   = r.get("filter_only", False)

    mode_label   = "FILTER BROWSE" if filter_only else mode.upper()
    filter_parts = [f"{k.replace('_',' ').title()}: {v}" for k,v in r["sidebar"].items() if v]
    filter_label = ", ".join(filter_parts) if filter_parts else "None"
    doc_found    = f"{len(filtered_docs):,}"
    if filter_only:
        stats = f'<div class="stats-bar"><div class="stat-item">Mode: <span class="stat-value">{mode_label}</span></div><div class="stat-item">Documents found: <span class="stat-value">{doc_found}</span></div><div class="stat-item">Filters: <span class="stat-value">{filter_label}</span></div></div>'
    else:
        passages = str(len(chunk_rows))
        stats = f'<div class="stats-bar"><div class="stat-item">Mode: <span class="stat-value">{mode_label}</span></div><div class="stat-item">Documents found: <span class="stat-value">{doc_found}</span></div><div class="stat-item">Passages: <span class="stat-value">{passages}</span></div><div class="stat-item">Filters: <span class="stat-value">{filter_label}</span></div></div>'
    st.markdown(stats, unsafe_allow_html=True)

    if "highlight_source" not in st.session_state:
        st.session_state.highlight_source = None
    highlight = st.session_state.highlight_source

    seen_src, unique_chunks = set(), []
    for row in chunk_rows:
        if row[1] not in seen_src: seen_src.add(row[1]); unique_chunks.append(row)

    path_map = {}
    if unique_chunks:
        conn = get_db(); cur = conn.cursor()
        dids = [row[1] for row in unique_chunks]
        ph   = ",".join(["%s"]*len(dids))
        cur.execute(f"SELECT document_id,file_path FROM documents WHERE document_id IN ({ph})", dids)
        path_map = {row[0]:row[1] for row in cur.fetchall()}
        cur.close(); conn.close()

    if "active_tab" not in st.session_state:
        st.session_state.active_tab = 0

    tab_labels = ["✦  Answer", "Source Documents", "All Matching Documents"]
    tab_cols = st.columns([1.2, 1.2, 1.6, 3])
    for i, label in enumerate(tab_labels):
        with tab_cols[i]:
            if st.button(label, key=f"tab_btn_{i}", use_container_width=True):
                st.session_state.active_tab = i
                st.rerun()
    st.markdown('<hr style="margin:0 0 1.2rem;border-color:#E8ECF2"/>', unsafe_allow_html=True)

    active = st.session_state.active_tab

    if active == 0:
        if filter_only:
            st.markdown('<div class="empty-state"><div class="empty-icon">◈</div><div class="empty-title">Filter Browse Mode</div><div class="empty-text">Your filtered documents are in the All Matching Documents tab.<br>Type a question to get an AI-generated answer.</div></div>', unsafe_allow_html=True)
        elif chunk_rows:
            import re
            ans_text = clean_answer(answer)
            parts = re.split(r"(\[SOURCE \d+\])", ans_text)
            ans_html_parts = []
            for part in parts:
                m = re.match(r"\[SOURCE (\d+)\]", part)
                if m:
                    n = m.group(1)
                    ans_html_parts.append(f'<span class="citation-ref">[{n}]</span>')
                else:
                    ans_html_parts.append(part.replace("\n","<br>"))
            ans_html = "".join(ans_html_parts)
            st.markdown(f'<div class="answer-block"><div class="answer-label">✦ Analysis</div><div class="answer-text">{ans_html}</div></div>', unsafe_allow_html=True)

            st.markdown('<div class="sources-header">Referenced Sources</div>', unsafe_allow_html=True)
            for i, (cid,did,fname,mgr,asset,dtype,ddate,page,text) in enumerate(unique_chunks):
                tc = "notes-badge" if dtype=="Notes" else "marketing-badge"
                sc1, sc2 = st.columns([6, 1])
                with sc1:
                    st.markdown(f'<div style="padding:0.5rem 0;border-bottom:1px solid #E8ECF2"><span class="asset-badge">{asset}</span><span class="type-badge {tc}">{dtype}</span> <b style="font-size:0.85rem">{fname}</b> <span style="font-size:0.75rem;color:#8A96A8">· Page {page}</span></div>', unsafe_allow_html=True)
                with sc2:
                    if st.button("View", key=f"jump_{cid}"):
                        st.session_state.active_tab = 1
                        st.session_state.highlight_source = did
                        st.rerun()
        else:
            st.markdown('<div class="empty-state"><div class="empty-icon">◈</div><div class="empty-title">No passages found</div><div class="empty-text">Try broadening your search or adjusting filters.</div></div>', unsafe_allow_html=True)

    elif active == 1:
        if unique_chunks:
            st.markdown(f'<p style="font-size:0.8rem;color:#8A96A8;margin-bottom:1rem">{len(unique_chunks)} source passages retrieved</p>', unsafe_allow_html=True)
            for cid,did,fname,mgr,asset,dtype,ddate,page,text in unique_chunks:
                tc = "notes-badge" if dtype=="Notes" else "marketing-badge"
                is_highlighted = (highlight == did)
                if is_highlighted:
                    st.session_state.highlight_source = None
                border_color = "#C9A96E" if is_highlighted else "#1B2A4A"
                bg_color     = "#FFFDF7" if is_highlighted else "#FFFFFF"
                ref_label = '<div style="font-size:0.65rem;color:#C9A96E;font-weight:700;letter-spacing:0.1em;margin-bottom:0.4rem">▶ REFERENCED IN ANSWER</div>' if is_highlighted else ""
                excerpt = text[:320] + ("..." if len(text)>320 else "")
                card_html = f'<div class="result-card" style="border-left-color:{border_color};background:{bg_color}">{ref_label}<div class="result-filename">{fname}</div><div class="result-meta"><span class="asset-badge">{asset}</span><span class="type-badge {tc}">{dtype}</span> {mgr} · {ddate} · Page {page}</div><div class="result-excerpt">{excerpt}</div></div>'
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state"><div class="empty-icon">◈</div><div class="empty-title">No source documents retrieved</div></div>', unsafe_allow_html=True)

    elif active == 2:
        if filtered_docs:
            st.markdown(f'<p style="font-size:0.8rem;color:#8A96A8;margin-bottom:1rem">{len(filtered_docs):,} documents match your filters</p>', unsafe_allow_html=True)
            conn = get_db(); cur = conn.cursor()
            ids  = [r[0] for r in filtered_docs[:100]]
            ph   = ",".join(["%s"]*len(ids))
            cur.execute(f"SELECT document_id,file_path FROM documents WHERE document_id IN ({ph})", ids)
            pm = {r[0]:r[1] for r in cur.fetchall()}; cur.close(); conn.close()
            for doc_id,fname,mgr,asset,dtype,ddate,ext in filtered_docs[:100]:
                tc = "notes-badge" if dtype=="Notes" else "marketing-badge"
                st.markdown(f'<div class="result-card"><div class="result-filename">{fname}</div><div class="result-meta"><span class="asset-badge">{asset} — {ASSET_LABELS.get(asset,"")}</span><span class="type-badge {tc}">{dtype}</span> {mgr} · {ddate} · {ext.upper().replace(".","")}</div></div>', unsafe_allow_html=True)
            if len(filtered_docs) > 100:
                st.markdown(f'<p style="font-size:0.75rem;color:#8A96A8;text-align:center;margin-top:0.8rem">Showing first 100 of {len(filtered_docs):,} — refine filters to narrow results.</p>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state"><div class="empty-icon">◈</div><div class="empty-title">No documents match current filters</div></div>', unsafe_allow_html=True)

else:
    st.markdown("""
    <div class="empty-state">
        <div class="empty-icon">✦</div>
        <div class="empty-title">Document Intelligence Platform</div>
        <div class="empty-text">
            Search across your entire document corpus using natural language.<br>
            Use the filters above to narrow by asset class, manager, type, or year.<br><br>
            <strong>Try:</strong> "Show me all PE marketing materials from Blackstone" ·
            "What are the fee structures across our credit funds?" ·
            "Extract IRR data from Rialto documents"
        </div>
    </div>
    """, unsafe_allow_html=True)

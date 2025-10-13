"""
LTC Insurance Analytics - PREMIUM Edition
Enterprise-grade Streamlit in Snowflake with extraordinary UX
"""

import streamlit as st
from snowflake.snowpark.context import get_active_session
from snowflake.snowpark.functions import (
    col, sum as sum_, avg, count, lit, last_day, to_timestamp, 
    when, count_distinct, max as max_, min as min_, datediff
)
from datetime import date, datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Optional, Dict, Any, List
import time

# ============================================================================
# Configuration & Styling
# ============================================================================

st.set_page_config(
    page_title="LTC Insurance Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/s685/ltc-insurance-platform',
        'Report a bug': 'https://github.com/s685/ltc-insurance-platform/issues',
        'About': "# LTC Insurance Analytics Platform\n### Powered by Snowflake + Streamlit"
    }
)

# Custom CSS for premium look
st.markdown("""
<style>
    /* Premium color scheme */
    :root {
        --primary-color: #1f77b4;
        --success-color: #00CC96;
        --warning-color: #FFA15A;
        --danger-color: #EF553B;
    }
    
    /* Animated gradient background for header */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
        animation: gradient 15s ease infinite;
        background-size: 200% 200%;
    }
    
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Metric cards with hover effect */
    .stMetric {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid var(--primary-color);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .stMetric:hover {
        transform: translateY(-5px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
    
    /* Improved dataframe styling */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Custom button styling */
    .stButton>button {
        border-radius: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        font-weight: 600;
        transition: all 0.3s;
    }
    
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #f8f9fa;
    }
    
    /* Success message styling */
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Warning message styling */
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Info box styling */
    .info-box {
        background-color: #d1ecf1;
        border-left: 4px solid #17a2b8;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Chart container */
    .chart-container {
        background-color: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin: 1rem 0;
    }
    
    /* Pulse animation for important metrics */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    
    .pulse {
        animation: pulse 2s infinite;
    }
</style>
""", unsafe_allow_html=True)

# Get Snowpark session
session = get_active_session()

# Constants
CLAIMS_TABLE = "LTC_INSURANCE.ANALYTICS.CLAIMS_TPA_FEE_WORKSHEET_SNAPSHOT_FACT"
POLICY_TABLE = "LTC_INSURANCE.ANALYTICS.POLICY_MONTHLY_SNAPSHOT_FACT"

# Session state initialization
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'comparison_mode' not in st.session_state:
    st.session_state.comparison_mode = False
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

# ============================================================================
# Premium Formatter Functions
# ============================================================================

def format_currency(value, decimals=2):
    """Format with currency symbol and color coding."""
    if value is None:
        return "N/A"
    try:
        num = float(value)
        formatted = f"${num:,.{decimals}f}"
        return formatted
    except:
        return str(value)

def format_number(value, decimals=0):
    """Format with thousand separators."""
    if value is None:
        return "N/A"
    try:
        num = float(value)
        if decimals == 0:
            return f"{int(num):,}"
        return f"{num:,.{decimals}f}"
    except:
        return str(value)

def format_percentage(value, decimals=1):
    """Format as percentage with emoji indicators."""
    if value is None:
        return "N/A"
    try:
        num = float(value)
        emoji = "📈" if num > 0 else "📉" if num < 0 else "➡️"
        return f"{emoji} {num:.{decimals}f}%"
    except:
        return str(value)

def get_trend_indicator(current, previous):
    """Get trend indicator with arrow."""
    if previous == 0:
        return "➡️ N/A"
    change = ((current - previous) / previous) * 100
    if change > 5:
        return f"📈 +{change:.1f}%"
    elif change < -5:
        return f"📉 {change:.1f}%"
    else:
        return f"➡️ {change:.1f}%"

# ============================================================================
# Data Access with Smart Caching
# ============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_claims_summary(_session, carrier_name=None, report_end_dt=None):
    """Get comprehensive claims summary with performance metrics."""
    start_time = time.time()
    
    df = _session.table(CLAIMS_TABLE)
    
    # Core business logic filter
    core_filter = (
        ((col("ONGOING_RATE_MONTH") == 1) & col("IS_INITIAL_DECISION_FLAG").isin([0, 1])) |
        ((col("ONGOING_RATE_MONTH") == 0) & (col("IS_INITIAL_DECISION_FLAG") == 1)) |
        ((col("ONGOING_RATE_MONTH") == 2) & col("IS_INITIAL_DECISION_FLAG").isin([0, 1]))
    )
    df = df.filter(core_filter)
    
    if carrier_name:
        df = df.filter(col("CARRIER_NAME") == carrier_name)
    
    if report_end_dt:
        date_str = report_end_dt.strftime('%Y-%m-%d')
        df = df.filter(col("SNAPSHOT_DATE") == last_day(to_timestamp(lit(date_str))))
    
    # Aggregate metrics
    result = df.agg([
        count("*").alias("total_claims"),
        sum_(col("INITIAL_DECISIONS_FACILITIES")).alias("facility_claims"),
        sum_(col("INITIAL_DECISIONS_HOME_HEALTH")).alias("home_health_claims"),
        sum_(col("INITIAL_DECISIONS_ALL_OTHER")).alias("other_claims"),
        sum_(col("RETRO_ALL_FACILITIES") + col("RETRO_HOME_HEALTH") + col("RETRO_ALL_OTHER")).alias("total_retro_claims"),
        avg(col("RFB_PROCESS_TO_DECISION_TAT")).alias("avg_processing_time"),
        avg(col("RETRO_MONTHS")).alias("avg_retro_months"),
        max_(col("RFB_PROCESS_TO_DECISION_TAT")).alias("max_tat"),
        min_(col("RFB_PROCESS_TO_DECISION_TAT")).alias("min_tat")
    ]).collect()[0]
    
    summary = {k.lower(): float(v) if v is not None else 0.0 for k, v in result.as_dict().items()}
    
    # Decision counts
    approved = df.filter(col("DECISION") == "Approved").count()
    denied = df.filter(col("DECISION") == "Denied").count()
    in_assessment = df.filter(col("DECISION").isin(["In Assessment", "Pending"])).count()
    
    summary["approved_claims"] = float(approved)
    summary["denied_claims"] = float(denied)
    summary["in_assessment_claims"] = float(in_assessment)
    summary["approval_rate"] = (approved / summary.get("total_claims", 1) * 100) if summary.get("total_claims") > 0 else 0.0
    
    # Retro metrics
    total = summary.get("total_claims", 1)
    summary["retro_percentage"] = (summary.get("total_retro_claims", 0) / total * 100) if total > 0 else 0.0
    
    # Ongoing rate counts
    initial = df.filter(col("ONGOING_RATE_MONTH") == 0).count()
    ongoing = df.filter(col("ONGOING_RATE_MONTH") == 1).count()
    restoration = df.filter(col("ONGOING_RATE_MONTH") == 2).count()
    
    summary["initial_decisions"] = float(initial)
    summary["ongoing_decisions"] = float(ongoing)
    summary["restoration_decisions"] = float(restoration)
    
    # Performance metric
    summary["query_time"] = time.time() - start_time
    
    return summary

@st.cache_data(ttl=300, show_spinner=False)
def get_claims_list(_session, carrier_name=None, report_end_dt=None, limit=100):
    """Get detailed claims list."""
    df = _session.table(CLAIMS_TABLE)
    
    core_filter = (
        ((col("ONGOING_RATE_MONTH") == 1) & col("IS_INITIAL_DECISION_FLAG").isin([0, 1])) |
        ((col("ONGOING_RATE_MONTH") == 0) & (col("IS_INITIAL_DECISION_FLAG") == 1)) |
        ((col("ONGOING_RATE_MONTH") == 2) & col("IS_INITIAL_DECISION_FLAG").isin([0, 1]))
    )
    df = df.filter(core_filter)
    
    if carrier_name:
        df = df.filter(col("CARRIER_NAME") == carrier_name)
    
    if report_end_dt:
        date_str = report_end_dt.strftime('%Y-%m-%d')
        df = df.filter(col("SNAPSHOT_DATE") == last_day(to_timestamp(lit(date_str))))
    
    df = df.select(
        col("TPA_FEE_WORKSHEET_SNAPSHOT_FACT_ID").alias("Claim_ID"),
        col("POLICY_NUMBER").alias("Policy_Number"),
        col("CLAIMANTNAME").alias("Claimant_Name"),
        col("CARRIER_NAME").alias("Carrier"),
        col("DECISION").alias("Decision"),
        col("SNAPSHOT_DATE").alias("Snapshot_Date"),
        col("ONGOING_RATE_MONTH").alias("Rate_Month"),
        col("RFB_PROCESS_TO_DECISION_TAT").alias("TAT_Days")
    ).order_by(col("SNAPSHOT_DATE").desc()).limit(limit)
    
    return df.to_pandas()

@st.cache_data(ttl=300, show_spinner=False)
def get_policy_metrics(_session, carrier_name=None, snapshot_date=None):
    """Get comprehensive policy metrics."""
    start_time = time.time()
    
    df = _session.table(POLICY_TABLE)
    
    if carrier_name:
        df = df.filter(col("CARRIER_NAME") == carrier_name)
    
    if snapshot_date:
        date_str = snapshot_date.strftime('%Y-%m-%d')
        df = df.filter(col("POLICY_SNAPSHOT_DATE") == date_str)
    
    result = df.agg([
        count("*").alias("total_policies"),
        avg(col("RATED_AGE")).alias("avg_age"),
        sum_(col("ANNUALIZED_PREMIUM")).alias("total_premium"),
        avg(col("ANNUALIZED_PREMIUM")).alias("avg_premium"),
        sum_(col("LIFETIME_COLLECTED_PREMIUM")).alias("total_collected"),
        sum_(col("TOTAL_ACTIVE_CLAIMS")).alias("total_active_claims"),
        sum_(col("TOTAL_RFBS")).alias("total_rfbs"),
        sum_(col("TOTAL_APPROVED_RFBS")).alias("total_approved_rfbs"),
        count_distinct(col("INSURED_STATE")).alias("states_count")
    ]).collect()[0]
    
    metrics = {k.lower(): float(v) if v is not None else 0.0 for k, v in result.as_dict().items()}
    
    # Status counts
    in_waiver = df.filter(col("IN_WAIVER_FLG") == "Yes").count()
    in_forfeiture = df.filter(col("IN_NONFORFEITURE_FLG") == "Yes").count()
    active_policies = df.filter(col("POLICY_STATUS_DIM_ID").isin(["ACTIVE", "Active"])).count()
    
    metrics["in_waiver"] = float(in_waiver)
    metrics["in_forfeiture"] = float(in_forfeiture)
    metrics["active_policies"] = float(active_policies)
    
    total = metrics.get("total_policies", 1)
    metrics["lapse_rate"] = ((total - active_policies) / total * 100) if total > 0 else 0.0
    metrics["policies_with_claims"] = float(df.filter(col("TOTAL_ACTIVE_CLAIMS") > 0).count())
    metrics["avg_claims_per_policy"] = metrics.get("total_active_claims", 0) / total if total > 0 else 0.0
    
    # Performance metric
    metrics["query_time"] = time.time() - start_time
    
    return metrics

@st.cache_data(ttl=300, show_spinner=False)
def get_state_distribution(_session, carrier_name=None, snapshot_date=None, top_n=10):
    """Get geographic distribution."""
    df = _session.table(POLICY_TABLE)
    
    if carrier_name:
        df = df.filter(col("CARRIER_NAME") == carrier_name)
    
    if snapshot_date:
        date_str = snapshot_date.strftime('%Y-%m-%d')
        df = df.filter(col("POLICY_SNAPSHOT_DATE") == date_str)
    
    result = df.group_by("INSURED_STATE").agg([
        count("*").alias("policy_count"),
        sum_(col("ANNUALIZED_PREMIUM")).alias("total_premium")
    ]).order_by(col("policy_count").desc()).limit(top_n).to_pandas()
    
    return result

@st.cache_data(ttl=300, show_spinner=False)
def get_policy_list(_session, carrier_name=None, snapshot_date=None, limit=100):
    """Get detailed policy list."""
    df = _session.table(POLICY_TABLE)
    
    if carrier_name:
        df = df.filter(col("CARRIER_NAME") == carrier_name)
    
    if snapshot_date:
        date_str = snapshot_date.strftime('%Y-%m-%d')
        df = df.filter(col("POLICY_SNAPSHOT_DATE") == date_str)
    
    df = df.select(
        col("POLICY_ID").alias("Policy_ID"),
        col("CARRIER_NAME").alias("Carrier"),
        col("INSURED_STATE").alias("State"),
        col("POLICY_STATUS_DIM_ID").alias("Status"),
        col("ANNUALIZED_PREMIUM").alias("Annual_Premium"),
        col("RATED_AGE").alias("Age"),
        col("IN_WAIVER_FLG").alias("In_Waiver"),
        col("TOTAL_ACTIVE_CLAIMS").alias("Active_Claims")
    ).order_by(col("ANNUALIZED_PREMIUM").desc()).limit(limit)
    
    return df.to_pandas()

# ============================================================================
# AI-Powered Insights Generator
# ============================================================================

def generate_smart_insights(summary_data, data_type="claims"):
    """Generate AI-like insights from data."""
    insights = []
    
    if data_type == "claims":
        total = summary_data.get("total_claims", 0)
        approval_rate = summary_data.get("approval_rate", 0)
        avg_tat = summary_data.get("avg_processing_time", 0)
        
        # Approval rate insights
        if approval_rate > 80:
            insights.append(("🎯 **Excellent Performance**", 
                           f"Approval rate of {approval_rate:.1f}% exceeds industry benchmark of 75%"))
        elif approval_rate < 60:
            insights.append(("⚠️ **Action Required**", 
                           f"Approval rate of {approval_rate:.1f}% is below target. Review denial reasons."))
        
        # TAT insights
        if avg_tat < 25:
            insights.append(("⚡ **Fast Processing**", 
                           f"Average TAT of {avg_tat:.1f} days is {25-avg_tat:.1f} days faster than target"))
        elif avg_tat > 35:
            insights.append(("🐌 **Slow Processing**", 
                           f"Average TAT of {avg_tat:.1f} days exceeds 30-day target. Consider staffing review."))
        
        # Volume insights
        if total > 100:
            insights.append(("📊 **High Volume Period**", 
                           f"Processing {total} claims. Monitor capacity closely."))
    
    else:  # policy insights
        total = summary_data.get("total_policies", 0)
        lapse_rate = summary_data.get("lapse_rate", 0)
        total_premium = summary_data.get("total_premium", 0)
        
        # Lapse rate insights
        if lapse_rate < 5:
            insights.append(("✨ **Strong Retention**", 
                           f"Lapse rate of {lapse_rate:.1f}% indicates excellent policy retention"))
        elif lapse_rate > 10:
            insights.append(("⚠️ **Retention Risk**", 
                           f"Lapse rate of {lapse_rate:.1f}% requires attention. Review customer satisfaction."))
        
        # Premium insights
        avg_prem = total_premium / total if total > 0 else 0
        if avg_prem > 4000:
            insights.append(("💰 **Premium Portfolio**", 
                           f"Average premium of ${avg_prem:,.0f} indicates high-value policies"))
    
    return insights

# ============================================================================
# Premium Dashboard Components
# ============================================================================

def render_premium_header():
    """Render animated premium header."""
    st.markdown("""
    <div class="main-header">
        <h1 style='margin:0; font-size: 2.5rem;'>🏥 LTC Insurance Analytics</h1>
        <p style='margin:0; font-size: 1.2rem; opacity: 0.9;'>Enterprise Intelligence Platform • Powered by Snowflake</p>
    </div>
    """, unsafe_allow_html=True)

def render_quick_stats(metrics):
    """Render quick stats bar at top."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; color: white;'>
            <div style='font-size: 2rem; font-weight: bold;'>{format_number(metrics.get('total', 0))}</div>
            <div style='font-size: 0.9rem; opacity: 0.9;'>Total Records</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border-radius: 10px; color: white;'>
            <div style='font-size: 2rem; font-weight: bold;'>⚡</div>
            <div style='font-size: 0.9rem; opacity: 0.9;'>Real-time Data</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        query_time = metrics.get('query_time', 0)
        st.markdown(f"""
        <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); border-radius: 10px; color: white;'>
            <div style='font-size: 2rem; font-weight: bold;'>{query_time:.2f}s</div>
            <div style='font-size: 0.9rem; opacity: 0.9;'>Query Time</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); border-radius: 10px; color: white;'>
            <div style='font-size: 2rem; font-weight: bold;'>✓</div>
            <div style='font-size: 0.9rem; opacity: 0.9;'>Cached</div>
        </div>
        """, unsafe_allow_html=True)

def render_sidebar():
    """Render premium sidebar."""
    st.sidebar.markdown("## 🎯 Navigation")
    
    page = st.sidebar.radio(
        "Choose Dashboard",
        ["🏠 Executive Summary", "📋 Claims Analytics", "📊 Policy Analytics", "🔬 Advanced Analytics"],
        label_visibility="collapsed"
    )
    
    st.sidebar.divider()
    st.sidebar.markdown("## 🔍 Global Filters")
    
    # Quick filter presets
    preset = st.sidebar.selectbox(
        "Quick Presets",
        ["Custom", "Last Month", "Last Quarter", "YTD", "All Time"]
    )
    
    if preset == "Last Month":
        default_date = date.today().replace(day=1) - timedelta(days=1)
    elif preset == "Last Quarter":
        default_date = (date.today().replace(day=1) - timedelta(days=90))
    else:
        default_date = date(2024, 10, 31)
    
    carrier_name = st.sidebar.selectbox(
        "🏢 Carrier",
        ["All", "Acme Insurance Co", "Beta Health Insurance", "Gamma Long Term Care"],
        index=1
    )
    
    snapshot_date = st.sidebar.date_input(
        "📅 Snapshot Date",
        value=default_date
    )
    
    carrier_filter = None if carrier_name == "All" else carrier_name
    
    st.sidebar.divider()
    
    # Advanced options in expander
    with st.sidebar.expander("⚙️ Advanced Options"):
        st.session_state.comparison_mode = st.checkbox("📊 Comparison Mode", value=False)
        auto_refresh = st.checkbox("🔄 Auto Refresh (5min)", value=False)
        show_insights = st.checkbox("🤖 AI Insights", value=True)
    
    st.sidebar.divider()
    
    # Action buttons
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    with col2:
        if st.button("📥 Export", use_container_width=True):
            st.sidebar.success("Export queued!")
    
    # Footer
    st.sidebar.divider()
    st.sidebar.markdown("""
    <div style='text-align: center; padding: 1rem; background-color: #f8f9fa; border-radius: 8px;'>
        <div style='font-size: 0.8rem; color: #6c757d;'>
            ⚡ Powered by <strong>Snowflake</strong><br/>
            🚀 Built with <strong>Streamlit</strong><br/>
            📊 v1.0.0 Premium Edition
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    return page, carrier_filter, snapshot_date, st.session_state.get('comparison_mode', False), show_insights

# ============================================================================
# Dashboard Pages (Continued in next message due to length)
# ============================================================================

def render_executive_summary(carrier_name, snapshot_date):
    """Render executive summary dashboard."""
    st.markdown("### 📊 Executive Summary Dashboard")
    st.markdown("*High-level overview of key performance indicators*")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.spinner("Loading executive summary..."):
            claims_sum = get_claims_summary(session, carrier_name, snapshot_date)
            policy_metrics = get_policy_metrics(session, carrier_name, snapshot_date)
        
        st.success("✅ Data loaded successfully")
        
        # Combined metrics
        combined_metrics = {
            'total': claims_sum.get('total_claims', 0) + policy_metrics.get('total_policies', 0),
            'query_time': (claims_sum.get('query_time', 0) + policy_metrics.get('query_time', 0)) / 2
        }
        
        render_quick_stats(combined_metrics)
        
        st.markdown("---")
        
        # Key metrics in tabs
        tab1, tab2, tab3 = st.tabs(["📋 Claims Overview", "📊 Policy Overview", "🎯 Combined Insights"])
        
        with tab1:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Claims", format_number(claims_sum.get("total_claims", 0)))
            with col2:
                st.metric("Approval Rate", format_percentage(claims_sum.get("approval_rate", 0)))
            with col3:
                st.metric("Avg TAT", f"{claims_sum.get('avg_processing_time', 0):.1f} days")
            with col4:
                st.metric("Retro Claims", f"{claims_sum.get('retro_percentage', 0):.1f}%")
        
        with tab2:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Policies", format_number(policy_metrics.get("total_policies", 0)))
            with col2:
                st.metric("Active Rate", f"{100 - policy_metrics.get('lapse_rate', 0):.1f}%")
            with col3:
                st.metric("Total Premium", format_currency(policy_metrics.get("total_premium", 0), 0))
            with col4:
                st.metric("Avg Premium", format_currency(policy_metrics.get("avg_premium", 0)))
        
        with tab3:
            total_policies = policy_metrics.get("total_policies", 1)
            total_claims = claims_sum.get("total_claims", 0)
            claims_per_policy = (total_claims / total_policies) if total_policies > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Claims per Policy", f"{claims_per_policy:.2f}")
            with col2:
                st.metric("Revenue at Risk", format_currency(policy_metrics.get("total_premium", 0) * 0.05, 0))
            with col3:
                st.metric("States Covered", format_number(policy_metrics.get("states_count", 0)))
    
    with col2:
        st.markdown("### 🤖 AI-Powered Insights")
        
        # Generate insights for both
        claims_insights = generate_smart_insights(claims_sum, "claims")
        policy_insights = generate_smart_insights(policy_metrics, "policy")
        
        st.markdown("**📋 Claims Insights:**")
        for title, desc in claims_insights:
            st.markdown(f"""
            <div class="info-box">
                <strong>{title}</strong><br/>
                {desc}
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("**📊 Policy Insights:**")
        for title, desc in policy_insights:
            st.markdown(f"""
            <div class="info-box">
                <strong>{title}</strong><br/>
                {desc}
            </div>
            """, unsafe_allow_html=True)

def render_claims_dashboard(carrier_name, report_end_dt):
    """Render comprehensive claims analytics dashboard with premium features."""
    st.header("📋 Claims Analytics Dashboard")
    
    with st.spinner("🔄 Loading claims data..."):
        summary = get_claims_summary(session, carrier_name, report_end_dt)
        claims_df = get_claims_list(session, carrier_name, report_end_dt, 100)
    
    st.success("✅ Data loaded successfully!")
    
    # Quick stats bar
    render_quick_stats({'total': summary.get('total_claims', 0), 'query_time': summary.get('query_time', 0)})
    
    st.divider()
    
    # KPI Cards - Row 1
    st.subheader("Key Performance Indicators")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Claims",
            format_number(summary.get("total_claims", 0)),
            help="Total number of claims matching filters"
        )
    
    with col2:
        approval_rate = summary.get("approval_rate", 0)
        st.metric(
            "Approval Rate",
            format_percentage(approval_rate),
            delta=f"{int(summary.get('approved_claims', 0))} approved",
            help="Percentage of approved claims"
        )
    
    with col3:
        avg_tat = summary.get('avg_processing_time', 0)
        st.metric(
            "Avg Processing Time",
            f"{avg_tat:.1f} days",
            help="Average turnaround time (TAT)"
        )
    
    with col4:
        st.metric(
            "Retro Claims",
            f"{summary.get('retro_percentage', 0):.1f}%",
            delta=f"{int(summary.get('total_retro_claims', 0))} claims",
            help="Percentage of retroactive claims"
        )
    
    # KPI Cards - Row 2
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric(
            "Facility Claims",
            format_number(summary.get("facility_claims", 0)),
            help="Facility category claims"
        )
    
    with col6:
        st.metric(
            "Home Health",
            format_number(summary.get("home_health_claims", 0)),
            help="Home health category claims"
        )
    
    with col7:
        st.metric(
            "Denied Claims",
            format_number(summary.get("denied_claims", 0)),
            help="Total denied claims"
        )
    
    with col8:
        st.metric(
            "In Assessment",
            format_number(summary.get("in_assessment_claims", 0)),
            help="Claims currently in assessment"
        )
    
    st.divider()
    
    # AI Insights Section
    col_insights, col_charts = st.columns([1, 2])
    
    with col_insights:
        st.markdown("### 🤖 AI Insights")
        insights = generate_smart_insights(summary, "claims")
        
        for title, desc in insights:
            st.markdown(f"""
            <div class="info-box">
                <strong>{title}</strong><br/>
                {desc}
            </div>
            """, unsafe_allow_html=True)
        
        # Performance indicators
        st.markdown("### 📊 Benchmarks")
        if avg_tat < 25:
            st.success(f"✅ TAT is {25-avg_tat:.1f} days under target")
        elif avg_tat > 35:
            st.error(f"⚠️ TAT is {avg_tat-30:.1f} days over target")
        else:
            st.info(f"➡️ TAT is within acceptable range")
    
    with col_charts:
        # Charts in tabs
        tab1, tab2, tab3 = st.tabs(["📊 Decisions", "📈 Categories", "🔄 Rate Month"])
        
        with tab1:
            st.markdown("**Decision Breakdown**")
            decision_data = pd.DataFrame({
                "Decision": ["Approved", "Denied", "In Assessment"],
                "Count": [
                    summary.get("approved_claims", 0),
                    summary.get("denied_claims", 0),
                    summary.get("in_assessment_claims", 0)
                ]
            })
            fig = px.pie(
                decision_data, 
                values="Count", 
                names="Decision",
                color_discrete_sequence=["#00CC96", "#EF553B", "#FFA15A"],
                hole=0.4
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.markdown("**Category Breakdown**")
            category_data = pd.DataFrame({
                "Category": ["Facility", "Home Health", "Other"],
                "Count": [
                    summary.get("facility_claims", 0),
                    summary.get("home_health_claims", 0),
                    summary.get("other_claims", 0)
                ]
            })
            fig = px.bar(
                category_data, 
                x="Category", 
                y="Count",
                color="Category",
                color_discrete_sequence=["#636EFA", "#AB63FA", "#FFA15A"]
            )
            fig.update_layout(showlegend=False, xaxis_title="Category", yaxis_title="Number of Claims")
            st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            st.markdown("**Ongoing Rate Month Distribution**")
            ongoing_data = pd.DataFrame({
                "Type": ["Initial", "Ongoing", "Restoration"],
                "Count": [
                    summary.get("initial_decisions", 0),
                    summary.get("ongoing_decisions", 0),
                    summary.get("restoration_decisions", 0)
                ]
            })
            fig = px.bar(
                ongoing_data, 
                x="Type", 
                y="Count",
                color="Type",
                color_discrete_sequence=["#00CC96", "#636EFA", "#EF553B"]
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # Retroactive Analysis
    st.subheader("🔄 Retroactive Claims Analysis")
    col_left2, col_right2 = st.columns(2)
    
    with col_left2:
        retro_total = summary.get("total_retro_claims", 0)
        if retro_total > 0:
            retro_data = pd.DataFrame({
                "Category": ["Facility", "Home Health", "Other"],
                "Count": [
                    summary.get("facility_claims", 0) * 0.15,
                    summary.get("home_health_claims", 0) * 0.1,
                    summary.get("other_claims", 0) * 0.05
                ]
            })
            fig = px.bar(retro_data, x="Category", y="Count", color_discrete_sequence=["#FF6692"])
            fig.update_layout(title="Estimated Retro Claims by Category")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No retroactive claims in this period")
    
    with col_right2:
        avg_retro = summary.get("avg_retro_months", 0)
        if avg_retro > 0:
            st.markdown(f"""
            <div class="chart-container">
                <h4>Retro Metrics</h4>
                <p style='font-size: 2rem; font-weight: bold; color: #636EFA;'>{avg_retro:.1f} months</p>
                <p>Average Retroactive Period</p>
                <hr/>
                <p><strong>Total Retro Claims:</strong> {format_number(retro_total)}</p>
                <p><strong>Retro %:</strong> {summary.get('retro_percentage', 0):.1f}%</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No retro metrics available")
    
    st.divider()
    
    # Recent Claims Table with enhanced display
    st.subheader("📋 Recent Claims")
    st.markdown(f"*Showing {len(claims_df)} most recent claims*")
    
    if not claims_df.empty:
        # Format the dataframe
        display_df = claims_df.copy()
        if 'TAT_Days' in display_df.columns:
            display_df['TAT_Days'] = display_df['TAT_Days'].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "N/A")
        
        st.dataframe(display_df, height=400)
        
        # Download section
        col_dl1, col_dl2, col_dl3 = st.columns([2, 1, 1])
        with col_dl1:
            csv = claims_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Claims Data (CSV)",
                data=csv,
                file_name=f"claims_export_{report_end_dt}.csv",
                mime="text/csv"
            )
        with col_dl2:
            st.metric("Records", len(claims_df))
        with col_dl3:
            st.metric("Columns", len(claims_df.columns))
    else:
        st.warning("⚠️ No claims data available for the selected filters.")

def render_policy_dashboard(carrier_name, snapshot_date):
    """Render comprehensive policy analytics dashboard with premium features."""
    st.header("📊 Policy Analytics Dashboard")
    
    with st.spinner("🔄 Loading policy data..."):
        metrics = get_policy_metrics(session, carrier_name, snapshot_date)
        state_dist = get_state_distribution(session, carrier_name, snapshot_date, 10)
        policy_df = get_policy_list(session, carrier_name, snapshot_date, 100)
    
    st.success("✅ Data loaded successfully!")
    
    # Quick stats bar
    render_quick_stats({'total': metrics.get('total_policies', 0), 'query_time': metrics.get('query_time', 0)})
    
    st.divider()
    
    # KPI Cards - Row 1
    st.subheader("Portfolio Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_policies = metrics.get("total_policies", 0)
        st.metric(
            "Total Policies",
            format_number(total_policies),
            help="Total number of policies"
        )
    
    with col2:
        active_policies = metrics.get("active_policies", 0)
        st.metric(
            "Active Policies",
            format_number(active_policies),
            delta=format_percentage((active_policies / total_policies * 100) if total_policies > 0 else 0),
            help="Currently active policies"
        )
    
    with col3:
        lapse_rate = metrics.get("lapse_rate", 0)
        st.metric(
            "Lapse Rate",
            format_percentage(lapse_rate),
            delta=f"{int(total_policies - active_policies)} lapsed",
            delta_color="inverse",
            help="Percentage of lapsed policies"
        )
    
    with col4:
        avg_premium = metrics.get("avg_premium", 0)
        st.metric(
            "Avg Premium",
            format_currency(avg_premium),
            help="Average annualized premium"
        )
    
    # KPI Cards - Row 2
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        total_revenue = metrics.get("total_premium", 0)
        st.metric(
            "Total Premium Revenue",
            format_currency(total_revenue, decimals=0),
            help="Total annualized premium revenue"
        )
    
    with col6:
        avg_age = metrics.get("avg_age", 0)
        st.metric(
            "Avg Insured Age",
            f"{avg_age:.1f} years" if avg_age > 0 else "N/A",
            help="Average age of insured lives"
        )
    
    with col7:
        in_waiver = metrics.get("in_waiver", 0)
        st.metric(
            "In Waiver",
            format_number(in_waiver),
            delta=format_percentage((in_waiver / total_policies * 100) if total_policies > 0 else 0),
            help="Policies in waiver status"
        )
    
    with col8:
        policies_with_claims = metrics.get("policies_with_claims", 0)
        st.metric(
            "With Active Claims",
            format_number(policies_with_claims),
            delta=format_percentage((policies_with_claims / total_policies * 100) if total_policies > 0 else 0),
            help="Policies with active claims"
        )
    
    # KPI Cards - Row 3
    col9, col10, col11, col12 = st.columns(4)
    
    with col9:
        total_claims = metrics.get("total_active_claims", 0)
        st.metric(
            "Total Active Claims",
            format_number(total_claims),
            help="Total active claims across all policies"
        )
    
    with col10:
        avg_claims = metrics.get("avg_claims_per_policy", 0)
        st.metric(
            "Avg Claims/Policy",
            f"{avg_claims:.2f}",
            help="Average claims per policy"
        )
    
    with col11:
        total_rfbs = metrics.get("total_rfbs", 0)
        approved_rfbs = metrics.get("total_approved_rfbs", 0)
        st.metric(
            "RFBs",
            format_number(total_rfbs),
            delta=f"{format_number(approved_rfbs)} approved",
            help="Request for benefits"
        )
    
    with col12:
        states_count = metrics.get("states_count", 0)
        st.metric(
            "States Covered",
            format_number(states_count),
            help="Number of states with policies"
        )
    
    st.divider()
    
    # AI Insights and Charts
    col_insights, col_charts = st.columns([1, 2])
    
    with col_insights:
        st.markdown("### 🤖 AI Insights")
        insights = generate_smart_insights(metrics, "policy")
        
        for title, desc in insights:
            st.markdown(f"""
            <div class="info-box">
                <strong>{title}</strong><br/>
                {desc}
            </div>
            """, unsafe_allow_html=True)
        
        # Key metrics summary
        st.markdown("### 💡 Quick Facts")
        st.markdown(f"""
        <div class="chart-container">
            <p>📍 <strong>Geographic Reach:</strong> {states_count} states</p>
            <p>💰 <strong>Total AUM:</strong> {format_currency(total_revenue, 0)}</p>
            <p>👥 <strong>Avg Age:</strong> {avg_age:.0f} years</p>
            <p>📊 <strong>Claim Rate:</strong> {(policies_with_claims/total_policies*100):.1f}%</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col_charts:
        # Charts in tabs
        tab1, tab2, tab3 = st.tabs(["📊 Status", "🏥 Waiver", "📈 Premium"])
        
        with tab1:
            st.markdown("**Active vs Lapsed Policies**")
            status_data = pd.DataFrame({
                "Status": ["Active", "Lapsed"],
                "Count": [
                    active_policies,
                    total_policies - active_policies
                ]
            })
            fig = px.pie(
                status_data, 
                values="Count", 
                names="Status",
                color_discrete_sequence=["#00CC96", "#EF553B"],
                hole=0.4
            )
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.markdown("**Waiver Status Breakdown**")
            waiver_data = pd.DataFrame({
                "Status": ["In Waiver", "In Forfeiture", "Standard"],
                "Count": [
                    metrics.get("in_waiver", 0),
                    metrics.get("in_forfeiture", 0),
                    total_policies - metrics.get("in_waiver", 0) - metrics.get("in_forfeiture", 0)
                ]
            })
            fig = px.bar(
                waiver_data, 
                x="Status", 
                y="Count",
                color="Status",
                color_discrete_sequence=["#636EFA", "#AB63FA", "#00CC96"]
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            st.markdown("**Premium Distribution**")
            avg_prem = total_revenue / total_policies if total_policies > 0 else 0
            st.markdown(f"""
            <div class="chart-container">
                <h3 style='color: #00CC96;'>{format_currency(avg_prem)}</h3>
                <p>Average Premium per Policy</p>
                <hr/>
                <p><strong>Total Portfolio:</strong> {format_currency(total_revenue, 0)}</p>
                <p><strong>Collected to Date:</strong> {format_currency(metrics.get('total_collected', 0), 0)}</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.divider()
    
    # Geographic Analysis
    st.subheader("🗺️ Geographic Analysis")
    
    if not state_dist.empty:
        col_left2, col_right2 = st.columns(2)
        
        with col_left2:
            st.markdown("**Top 10 States by Policy Count**")
            fig = px.bar(
                state_dist.head(10), 
                x="INSURED_STATE", 
                y="POLICY_COUNT",
                color="POLICY_COUNT",
                color_continuous_scale="Blues"
            )
            fig.update_layout(
                xaxis_title="State",
                yaxis_title="Number of Policies",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col_right2:
            st.markdown("**Premium Revenue by State**")
            state_dist_sorted = state_dist.sort_values("TOTAL_PREMIUM", ascending=True).tail(10)
            fig = px.bar(
                state_dist_sorted, 
                x="TOTAL_PREMIUM", 
                y="INSURED_STATE",
                orientation='h',
                color="TOTAL_PREMIUM",
                color_continuous_scale="Greens"
            )
            fig.update_layout(
                xaxis_title="Premium Revenue ($)",
                yaxis_title="State",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No geographic distribution data available")
    
    st.divider()
    
    # Recent Policies Table with enhanced display
    st.subheader("📋 Recent Policies")
    st.markdown(f"*Showing {len(policy_df)} most recent policies*")
    
    if not policy_df.empty:
        # Format the dataframe
        display_df = policy_df.copy()
        if 'Annual_Premium' in display_df.columns:
            display_df['Annual_Premium'] = display_df['Annual_Premium'].apply(
                lambda x: format_currency(float(x)) if pd.notna(x) else "N/A"
            )
        
        st.dataframe(display_df, height=400)
        
        # Download section
        col_dl1, col_dl2, col_dl3 = st.columns([2, 1, 1])
        with col_dl1:
            csv = policy_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Policy Data (CSV)",
                data=csv,
                file_name=f"policy_export_{snapshot_date}.csv",
                mime="text/csv"
            )
        with col_dl2:
            st.metric("Records", len(policy_df))
        with col_dl3:
            st.metric("Columns", len(policy_df.columns))
    else:
        st.warning("⚠️ No policy data available for the selected filters.")

def main():
    """Main application."""
    render_premium_header()
    page, carrier_filter, snapshot_date, comparison_mode, show_insights = render_sidebar()
    
    if page == "🏠 Executive Summary":
        render_executive_summary(carrier_filter, snapshot_date)
    elif page == "📋 Claims Analytics":
        render_claims_dashboard(carrier_filter, snapshot_date)
    elif page == "📊 Policy Analytics":
        render_policy_dashboard(carrier_filter, snapshot_date)
    else:
        st.info("🔬 Advanced analytics coming soon! Stay tuned for predictive models and ML insights.")

if __name__ == "__main__":
    main()


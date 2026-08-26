
from sqlalchemy import text
import pandas as pd
import streamlit as st
import datetime
import altair as alt

# --- 0. INITIAL CONFIGURATION ---
# Streamlit requires set_page_config to be the very first Streamlit command executed!
st.set_page_config(page_title="Pauliz PUB & Joint", layout="wide")

# Initialize session state for login status
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# --- BEAUTIFUL LOGIN INTERFACE FUNCTION ---
def login():
    # Inject Custom CSS for a beautiful, modern card login layout
    st.markdown("""
        <style>
        /* Hide default Streamlit sidebar and headers on the login screen */
        [data-testid="stSidebar"] { display: none; }
        [data-testid="stHeader"] { display: none; }
        
        /* Centered background container */
        .login-container {
            max-width: 450px;
            margin: 80px auto 20px auto;
            background: #ffffff;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.03);
            border: 1px solid #e2e8f0;
            text-align: center;
            font-family: 'Segoe UI', system-ui, sans-serif;
            animation: fadeIn 0.5s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .login-title {
            font-family: 'Consolas', sans-serif;
            color: #42c8f5;
            font-size: 42px;
            font-weight: 800;
            margin-bottom: 5px;
            letter-spacing: 1px;
        }
        
        .login-subtitle {
            color: #718096;
            font-size: 14px;
            margin-bottom: 30px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Render HTML Card structure snippet wrapper
    st.markdown("""
        <div class="login-container">
            <div class="login-title">Pauliz Business</div>
            <div class="login-subtitle">*Alert!* System access to only Authorised Individuals</div>
        </div>
    """, unsafe_allow_html=True)

    # Use a neat vertical column centering trick for the interactive widget element
    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            # 1. Added a unique 'key' to the text input
            password_input = st.text_input(
                "Enter system Password", 
                type="password", 
                help="Enter authorization key", 
                icon=":material/lock:",
                key="password_field" 
            )
            submit_button = st.form_submit_button("Verify password and Login", use_container_width=False)
    
            if submit_button:
                # Secure lookup from the passwords section
                system_password = st.secrets.get("passwords", {}).get("nedin")
        
                if system_password and password_input == system_password:
                    st.session_state.logged_in = True
                
                    # 2. Clear the password text field from session state
                    if "password_field" in st.session_state:
                        del st.session_state["password_field"]
                
                    st.success("Access Granted! Loading system...")
                    st.rerun()
                else:
                    st.error("🔒 Access Denied. Invalid password string.")

# Run Login Guard logic check block 
if not st.session_state.logged_in:
    login()
    st.stop() # Stops execution here so unauthenticated users see absolutely nothing else below

# --- 1. APP WORKSPACE CUSTOM GLOBAL STYLING ---
st.markdown("""
    <style>
    /* Base Editor Wrapper: Adds card styling and smooth glow on interaction */
    div[data-testid="stDataEditor"] {
        background-color: #ffffff;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        padding: 6px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    /* Focused Interaction: Changes border color to your brand signature color when editing */
    div[data-testid="stDataEditor"]:focus-within,
    div[data-testid="stDataEditor"]:hover {
        border-color: #ff4b4b;
        box-shadow: 0 10px 15px -3px rgba(255, 75, 75, 0.08), 0 4px 6px -2px rgba(255, 75, 75, 0.04);
    }

    /* Toolbar and Add Row Action Button Customization */
    div[data-testid="stDataEditor"] button {
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stDataEditor"] button:hover {
        background-color: #fff5f5 !important;
        color: #ff4b4b !important;
    }

    /* Streamlit Metric Cards Cohesiveness Layout */
    div[data-testid="stMetricValue"] {
        font-family: 'Segoe UI Mono', monospace !important;
        font-weight: 700 !important;
        color: #1a202c;
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. INITIALIZE POSTGRESQL NATIVE CONNECTION ---
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("🔒 PostgreSQL Database Connection Failed. Please check your network credentials.")
    st.exception(e)
    st.stop()

# Ensure mandatory editor tracking instance fields exist safely in session state
if "editor_session_id" not in st.session_state:
    st.session_state.editor_session_id = 0
if "row_count" not in st.session_state:
    st.session_state.row_count = 1

# Business Configuration Data fallbacks
BUSINESS_NAME = ["--Select Name--", "Pauliz Enterprise", "P&J Venture"]
TRANSACTION_OPTIONS = ["--Select Transaction--", "Sales", "Credit Sales", "Purchases", "Credit Purchases", "Expenses"]

# FIXED: Wrapped raw SQL multiline string explicitly using text()
with conn.session as session:
    session.execute(text("""
CREATE TABLE IF NOT EXISTS Particulars_Prices (
      particular_name VARCHAR(255) PRIMARY KEY,
      price NUMERIC(15, 2) DEFAULT 0.0,
      item_cost NUMERIC(15, 2) DEFAULT 0.0
 );
    """))
    session.execute(text("""
CREATE TABLE IF NOT EXISTS LNenterprise (
      id SERIAL PRIMARY KEY,
      date DATE,
      business_name VARCHAR(255),
      transaction_type VARCHAR(255),
      particulars VARCHAR(255),
      quantity INT,
      unit_price NUMERIC(15, 2),
      total_amount NUMERIC(15, 2),
      customer_name VARCHAR(255),
      contact_number VARCHAR(255),
      notes TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
    """))
    session.commit()
# Load mapping states out of relational tables 
PARTICULARS_MAP = {}
COST_MAP = {}
df_prices = conn.query("SELECT particular_name, price, item_cost FROM Particulars_Prices;", ttl=0)
if not df_prices.empty:
    for _, row in df_prices.iterrows():
        p_name = str(row["particular_name"]).strip()
        if p_name:
            PARTICULARS_MAP[p_name] = float(row["price"])
            COST_MAP[p_name] = float(row["item_cost"])

# --- SIDEBAR NAVIGATION ---
st.sidebar.write(
    '<p style="font-family: Consolas; color: #4e6291; font-size: 20px; font-weight: bold; text-align: Left; margin-bottom: 20px;">🎯 Pauliz P&J System</p>',
    unsafe_allow_html=True,
)
selection = st.sidebar.radio("Go to page:", ["Home", "New Transaction Entry", "Price List"])

# Add a logout action cleanly inside the bottom of your sidebar panel
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Log Out the System Account", use_container_width=False):
    st.session_state.logged_in = False
    st.rerun()

# --- MAIN PAGE ROUTING CONTENT ---
st.subheader(f"📍 {selection}")
if selection == "Home":
    st.write(
        '<p style="font-family: Consolas; color: #4e6291; font-size: 15px; font-weight: bold; text-align: Left; margin-bottom: 20px;">Navigate Core business Updates</p>',
        unsafe_allow_html=True,
    )

    # 1. FETCH FRESH DATA FROM POSTGRESQL (No caching ensures instant update visibility)
    try:
        query = """
            SELECT id, date, business_name, transaction_type, particulars, quantity, unit_price, total_amount, notes 
            FROM LNenterprise 
            ORDER BY date DESC, id DESC;
        """
        df = conn.query(query, ttl=0)  
    except Exception as db_err:
        st.error(f"❌ Error retrieving records from PostgreSQL: {db_err}")
        df = pd.DataFrame() 

    # Clean date data types safely using database lowercase labels
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors='coerce')
        valid_dates = df["date"].dropna()
    else:
        valid_dates = pd.Series()

    # Define date bounds safely based on database structural metrics
    default_start = valid_dates.min().date() if not valid_dates.empty else None
    default_end = valid_dates.max().date() if not valid_dates.empty else None

    # Initialize tracking infrastructure elements inside Session State
    if "col_sel_key" not in st.session_state: st.session_state.col_sel_key = "None"
    if "sec_col_select_key" not in st.session_state: st.session_state.sec_col_select_key = "None"
    if "start_date_key" not in st.session_state: st.session_state.start_date_key = default_start
    if "end_date_key" not in st.session_state: st.session_state.end_date_key = default_end

    def clear_all_filters():
        st.session_state.col_sel_key = "None" 
        st.session_state.sec_col_select_key = "None"
        st.session_state.start_date_key = default_start
        st.session_state.end_date_key = default_end
        for key in list(st.session_state.keys()):
            if key.startswith("val_sel_key_") or key.startswith("sec_val_key_"):
                del st.session_state[key]

    st.sidebar.button("🧹 Clear All Filters", on_click=clear_all_filters, use_container_width=True)

    # 2. Sidebar Configuration Layout
    st.sidebar.header("⏳ Date Options")
    start_date = st.sidebar.date_input("Start Date", value=st.session_state.start_date_key, key="start_date_key")
    end_date = st.sidebar.date_input("End Date", value=st.session_state.end_date_key, key="end_date_key")

    # Filter dataset by chosen dates
    filtered_df = df.copy()
    if not filtered_df.empty and "date" in filtered_df.columns and start_date and end_date:
        filtered_df = filtered_df[(filtered_df["date"].dt.date >= start_date) & (filtered_df["date"].dt.date <= end_date)]

    st.sidebar.markdown("---")
    st.sidebar.header("Filter by Record Type")

    # Columns excluded from acting as filter categories
    ignore_cols = ["id", "date", "quantity", "unit_price", "total_amount", "notes"]
    available_filter_columns = [col for col in filtered_df.columns if col not in ignore_cols]

    selected_column = st.sidebar.selectbox(
        "Select Column to Filter By",
        options=["None"] + available_filter_columns,
        key="col_sel_key"
    )

    # --- PRIMARY LEVEL FILTER ---
    selected_values = []
    if selected_column != "None" and not filtered_df.empty:
        unique_values = sorted([v for v in filtered_df[selected_column].astype(str).str.strip().unique() if v != ""])
        selected_values = st.sidebar.multiselect(
            f"Select Values for {selected_column}",
            options=unique_values,
            key=f"val_sel_key_{selected_column}"
        )
        if selected_values:
            filtered_df = filtered_df[filtered_df[selected_column].astype(str).str.strip().isin(selected_values)]

    # --- SECONDARY LEVEL FILTER ---
    secondary_values = []
    if selected_column != "None" and not filtered_df.empty:
        st.sidebar.markdown("---") 
        available_secondary_cols = ["None"] + [col for col in filtered_df.columns if col not in [selected_column] + ignore_cols]
        secondary_column = st.sidebar.selectbox(
            "Select Secondary Filter Column",
            options=available_secondary_cols,
            key="sec_col_select_key"
        )
        
        if secondary_column != "None":
            sec_unique_values = sorted([v for v in filtered_df[secondary_column].astype(str).str.strip().unique() if v != ""])
            secondary_values = st.sidebar.multiselect(
                f"Select Values for {secondary_column}",
                options=sec_unique_values,
                key=f"sec_val_key_{secondary_column}"
            )
            if secondary_values:
                filtered_df = filtered_df[filtered_df[secondary_column].astype(str).str.strip().isin(secondary_values)]


    #st.sidebar.markdown("---")
    # Reset Action Button (Triggers rerun instantly via callback)
    st.sidebar.button("🧹 Clear All Filters", on_click=clear_all_filters, use_container_width=True)

    # [Keep your previous Session State and Sidebar Filter logic here]

    # 3. Apply Multi-Stage Filtering Logic
    if selected_column != "None" and selected_values:
        filtered_df = filtered_df[filtered_df[selected_column].astype(str).str.strip().isin(selected_values)]

    if "Date" in filtered_df.columns and start_date and end_date:
        start_datetime = pd.to_datetime(start_date)
        end_datetime = pd.to_datetime(end_date)
        filtered_df = filtered_df[
            (filtered_df["Date"] >= start_datetime) & 
            (filtered_df["Date"] <= end_datetime)
        ]

    # Explicitly target your confirmed dataframe column keys
    type_col = "Transaction"
    amount_col = "Amount"

    # 4. Main Page Display & Download Action
    st.write(
            '<p style="font-family: Consolas; color: #4e6291; font-size: 25px; font-weight: bold; text-align: left; margin-bottom: 20px;">📋Business Records</p>',
            unsafe_allow_html=True,
        )

    if not filtered_df.empty:
        # --- METRICS SECTION START ---
        total_count = len(filtered_df)
        total_sum = 0.0

        # Create an explicit temporary copy for parsing types cleanly without modifying UI data
        calc_df = filtered_df.copy()
        if type_col in calc_df.columns and amount_col in calc_df.columns:
            calc_df[type_col] = calc_df[type_col].astype(str).str.strip().str.lower()
            calc_df[amount_col] = pd.to_numeric(calc_df[amount_col], errors='coerce').fillna(0)

            # 1. Isolate entries strictly to avoid overlap calculations
            c_sale_mask = calc_df[type_col] == "credit sale"
            sale_mask = (calc_df[type_col] == "sale") | ((calc_df[type_col].str.contains("sale", na=False)) & (~c_sale_mask))
        
            c_purch_mask = calc_df[type_col] == "credit purchase"
            purch_mask = (calc_df[type_col] == "purchase") | ((calc_df[type_col].str.contains("purchase", na=False)) & (~c_purch_mask))
        
            exp_mask = calc_df[type_col].str.contains("expense", na=False)
            debt_biz_mask = calc_df[type_col].str.contains("debt settlement business", na=False)
            debt_cred_mask = calc_df[type_col].str.contains("debt settlement creditor", na=False)

            # 2. Extract accurate operational metric totals
            sales_total = calc_df[sale_mask][amount_col].sum()
            credit_sales_total = calc_df[c_sale_mask][amount_col].sum()
            purchases_total = calc_df[purch_mask][amount_col].sum()
            credit_purchases_total = calc_df[c_purch_mask][amount_col].sum()
            expenses_total = calc_df[exp_mask][amount_col].sum()
            debt_biz_total = calc_df[debt_biz_mask][amount_col].sum()
            debt_cred_total = calc_df[debt_cred_mask][amount_col].sum()

            # 3. Correct Accounting Logic for Negative Outflows (EXCLUDING DEBT SETTLEMENTS)
            # Because purchases and expenses are already negative, we use '+' to let them subtract naturally.
            net_amount = sales_total + credit_sales_total + purchases_total + credit_purchases_total + expenses_total
            total_sum = net_amount

        metric_label = f"{', '.join(selected_values)}" if selected_values else "All Categories"
        if len(metric_label) > 30:
            metric_label = metric_label[:27] + "..."

        # Dynamic theme colors based on financial performance
        if total_sum > 0:
            text_color = "#2e7d32"      
            border_color = "#a5d6a7"    
            hover_border = "#2e7d32"    
            bg_glow = "rgba(46, 125, 50, 0.05)"
        elif total_sum < 0:
            text_color = "#d32f2f"      
            border_color = "#ef9a9a"    
            hover_border = "#d32f2f"    
            bg_glow = "rgba(211, 47, 47, 0.05)"
        else:
            text_color = "#1c1c1c"      
            border_color = "#e0e0e0"    
            hover_border = "#ff4b4b"    
            bg_glow = "rgba(0,0,0,0.05)"

        # Injecting modern responsive layout CSS with dynamic color hooks
        st.markdown(
            f"""
            <style>
            .metric-container {{
                background-color: #f8f9fa;
                border: 1px solid #e0e0e0;
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
                transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
            }}
            .metric-container:hover {{
                transform: translateY(-4px);
                box-shadow: 4px 8px 15px rgba(0,0,0,0.1);
                border-color: #ff4b4b;
            }}
            .financial-metric {{
                border-color: {border_color};
                background-color: {bg_glow};
            }}
            .financial-metric:hover {{
                border-color: {hover_border} !important;
            }}
            .metric-title {{ font-size: 14px; color: #6c757d; text-transform: uppercase; letter-spacing: 1px; }}
            .metric-value {{ font-size: 28px; font-weight: bold; color: #1c1c1c; margin-top: 5px; }}
            .metric-value-dynamic {{ font-size: 28px; font-weight: bold; color: {text_color}; margin-top: 5px; }}
            .metric-subtitle {{ font-size: 12px; color: #888888; margin-top: 5px; }}
            </style>
            """,
            unsafe_allow_html=True
        )

        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.markdown(f'<div class="metric-container"><div class="metric-title">Transactions Count</div><div class="metric-value">{total_count:,}</div><div class="metric-subtitle">Matching scope rows</div></div>', unsafe_allow_html=True)
        with m_col2:
            formatted_sum = f"Ugx{total_sum:,}" if total_sum >= 0 else f"-Ugx{abs(total_sum):,}"
    
            st.markdown(
                f"""
                <div class="metric-container financial-metric">
                    <div class="metric-title">Net Balance</div>
                    <div class="metric-value-dynamic">{formatted_sum}</div>
                    <div class="metric-subtitle">Filtered by: {metric_label}</div>
                </div>
                """, 
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Detailed Table view display
        display_df = filtered_df.copy()
        if "Date" in display_df.columns:
            display_df["Date"] = display_df["Date"].dt.strftime('%Y-%m-%d')
        st.dataframe(display_df, use_container_width=True)

        # CSV Exporter Component
        csv = filtered_df.to_csv(index=False)
        st.download_button(label="Export as CSV", data=csv, file_name="filtered_transactions.csv", mime="text/csv")

        # --- GRAPH GENERATION START ---
        st.markdown("---")
        st.write(
            '<p style="font-family: Consolas; color: #695e82; font-size: 25px; font-weight: bold; text-align: left; margin-bottom: 20px;">📊Networth Transaction Graphical Display</p>',
            unsafe_allow_html=True,
        )
        if type_col in filtered_df.columns and amount_col in filtered_df.columns:
            # 1. Define your exact desired sequence order
            desired_order = [
                "Net Amount",
                "Sales",
                "Credit Sales",
                "Purchases",
                "Credit Purchases",
                "Expenses",
                "Debt settlement business",
                "Debt settlement creditor",
            ]

            # 2. Build the dataframe
            plot_data = pd.DataFrame(
                {
                    "Transaction Type": desired_order,
                    "Total Amount (Ugx)": [
                        net_amount,
                        sales_total,
                        credit_sales_total,
                        purchases_total,
                        credit_purchases_total,
                        expenses_total,
                        debt_biz_total,
                        debt_cred_total,
                    ],
                }
            )

            # 3. Create an Altair bar chart with explicit grid and sorting controls
            chart = (
                alt.Chart(plot_data)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "Transaction Type:N",
                        sort=desired_order,  # Locks the bar order perfectly
                        axis=alt.Axis(
                            labelAngle=-45
                        ),  # Tilts text so categories don't overlap
                    ),
                    y=alt.Y(
                        "Total Amount (Ugx):Q",
                        axis=alt.Axis(grid=True),  # Forces clean horizontal grid lines
                    ),
                    color=alt.Color(
                        "Transaction Type:N",
                        scale=alt.Scale(scheme="tableau10"),  # Optional neat color palette
                        legend=None,  # Hides redundant legend to maximize screen width
                    ),
                )
            )

            # 4. Display via Streamlit's native Altair bridge
            st.altair_chart(chart, use_container_width=True)

            if net_amount >= 0:
                st.success(f"🟢 **Net Position:** Surplus of **Ugx{net_amount:,}**")
            else:
                st.error(f"🔴 **Net Position:** Deficit of **Ugx{abs(net_amount):,}**")
        else:
            st.warning(f"⚠️ Missing columns. Please verify that your file has `{type_col}` and `{amount_col}` fields.")

        # --- INVENTORY SECTION START ---
        st.markdown("---")
        st.write(
            '<p style="font-family: Consolas; color: #1e3d59; font-size: 25px; font-weight: bold; text-align: left; margin-bottom: 20px;">📦Inventory/Stock Monitoring</p>',
            unsafe_allow_html=True,
        )

        # Force the variable names to match exactly what your script uses below
        Particulars_col = "Particulars"   
        qty_col = "Quantity"             
        biz_name_col = "Business Name"   

        # Verify required inventory columns exist in your file structure
        if (Particulars_col in filtered_df.columns and 
            qty_col in filtered_df.columns and 
            type_col in filtered_df.columns and 
            biz_name_col in filtered_df.columns):
    
            # 1. Create inventory parsing copy
            inv_df = filtered_df.copy()
            inv_df[type_col] = inv_df[type_col].astype(str).str.strip().str.lower()
            inv_df[Particulars_col] = inv_df[Particulars_col].astype(str).str.strip()
            inv_df[biz_name_col] = inv_df[biz_name_col].astype(str).str.strip()
    
            # Force clean absolute numeric quantities
            inv_df[qty_col] = pd.to_numeric(inv_df[qty_col], errors='coerce').fillna(0).abs()

            # 2. Add an interactive UI dropdown to select which business to review
            unique_businesses = sorted(inv_df[biz_name_col].unique())
            selected_biz = st.selectbox("Select Business to view Stock Status", options=unique_businesses)
    
            # Filter dataset down to the chosen business location view
            biz_df = inv_df[inv_df[biz_name_col] == selected_biz]

            # 3. Segregate Stock In vs Stock Out using strict exact labels
            # 'purchases' and 'credit purchases' add to stock profiles
            stock_in_mask = biz_df[type_col].isin(["purchases", "credit purchases"])
            # 'sales' and 'credit sales' remove from stock profiles
            stock_out_mask = biz_df[type_col].isin(["sales", "credit sales"])

            # 4. Initialize separate tracking metrics mapped by item name
            stock_in_series = biz_df[stock_in_mask].groupby(Particulars_col)[qty_col].sum()
            stock_out_series = biz_df[stock_out_mask].groupby(Particulars_col)[qty_col].sum()

            # 5. Compile into a consolidated Master Stock Status Dataframe
            all_items = sorted(list(set(biz_df[Particulars_col].unique())))
    
            inventory_summary = pd.DataFrame(index=all_items)
            inventory_summary["Stock In (Qty)"] = inventory_summary.index.map(stock_in_series).fillna(0).astype(int)
            inventory_summary["Stock Out (Qty)"] = inventory_summary.index.map(stock_out_series).fillna(0).astype(int)
    
            # Balance: Stock In minus Stock Out
            inventory_summary["Current Stock Status"] = inventory_summary["Stock In (Qty)"] - inventory_summary["Stock Out (Qty)"]
            inventory_summary.index.name = "Item Description"
            inventory_summary = inventory_summary.reset_index()

            # 6. Display Interactive Stock Status Table with warning thresholds
            def highlight_stock(row):
                if row["Current Stock Status"] < 0:
                    return ["background-color: #fce8e6; color: #a81c0c;"] * len(row)
                elif row["Current Stock Status"] == 0:
                    return ["background-color: #fff3cd; color: #856404;"] * len(row)
                else:
                    return ["background-color: #e6f4ea; color: #137333;"] * len(row)

            styled_summary = inventory_summary.style.apply(highlight_stock, axis=1)
    
            st.markdown(f"##### Showing Stock breakdown for: **{selected_biz}**")
            st.dataframe(styled_summary, use_container_width=True)

            # 7. Render horizontal bar chart displaying current stock availability profiles
            st.markdown("##### 📈 Current Available Stock Visual")
            st.bar_chart(
                data=inventory_summary, 
                x="Item Description", 
                y="Current Stock Status", 
                use_container_width=True
            )

        else:
            st.warning(
                f"⚠️ **Inventory columns missing.** Ensure your file contains headers named: "
                f"`{Particulars_col}`, `{qty_col}`, and `{biz_name_col}` to render stock summary profiles."
    )
# --- INVENTORY SECTION END ---


# --- PAGE ROUTER: NEW TRANSACTION ENTRY ---
elif selection == "New Transaction Entry":
    available_items = ["--Select Item--"] + sorted(list(PARTICULARS_MAP.keys()))

    st.write(
            '<p style="font-family: Consolas; color: #4e6291; font-size: 15px; font-weight: bold; text-align: Left; margin-bottom: 20px;">Record Sales, Purchases, Expenses and stock</p>',
            unsafe_allow_html=True,
        )
        # --- MOBILE OPTIMIZATION: Inject CSS to force smooth mobile scrolling & clean column widths ---
    st.html(
        """
        <style>
        /* Force table container to adapt nicely on small mobile screens */
        [data-testid="stDataEditor"] {
            overflow-x: auto !important;
            max-width: 100% !important;
        }
        /* Make metrics readable on vertical mobile screens */
        [data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
        }
        </style>
        """
    )

    # --- 1. BATCH CONFIGURATION LINE ---
    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        tx_date = st.date_input("Transaction Date", datetime.date.today())
    with col_d2:
        business_name_sel = st.selectbox("Business Name", BUSINESS_NAME, key=f"bs_name_{st.session_state.editor_session_id}")
    with col_d3:
        global_tx_type = st.selectbox("Transaction Type", TRANSACTION_OPTIONS, key=f"tx_type_{st.session_state.editor_session_id}")

    # DETERMINE DYNAMIC TRANSACTION STATUS TRACKER TAG VALUE
    if global_tx_type in ["Credit Sales", "Credit Purchases"]:
        computed_status = "Pending"
    elif global_tx_type != "--Select Transaction--":
        computed_status = "Paid"
    else:
        computed_status = "Unknown"

    if global_tx_type != "--Select Transaction--":
        status_color = "🔴" if computed_status == "Pending" else "🟢"
        st.markdown(f"**Transaction Status Mode:** {status_color} **{computed_status}** *(Based on '{global_tx_type}')*")

    # --- COLUMN HEADERS LABELED EXPLICITLY ONCE ---
    h1, h2, h3, h4, h5 = st.columns([2.5, 1.2, 2.0, 2.0, 3.0])     
    with h1: st.markdown("**📦 Particulars Dropdown**")
    with h2: st.markdown("**🔢 Qty**")
    with h3: st.markdown("**🏷️ Unit Price (Ugx)**")
    with h4: st.markdown("**💰 Subtotal**")
    with h5: st.markdown("**📝 Description Notes**")

    rows_data = []
    live_total_amount = 0.0

    # --- 2. DYNAMIC INPUT ROWS SYSTEM ---
    for i in range(st.session_state.row_count):
        c1, c2, c3, c4, c5 = st.columns([2.5, 1.2, 2.0, 2.0, 3.0])

        current_session_prefix = st.session_state.editor_session_id
        part_key = f"part_{current_session_prefix}_{i}"
        qty_key = f"qty_{current_session_prefix}_{i}"
        price_key = f"price_{current_session_prefix}_{i}"
        notes_key = f"notes_{current_session_prefix}_{i}"

        def on_particular_change(row_index=i, pk=part_key, prk=price_key):
            current_selection = st.session_state.get(pk, "--Select Item--")
            if current_selection != "--Select Item--" and prk in st.session_state:
                st.session_state[prk] = int(PARTICULARS_MAP.get(current_selection, 0.0))

        with c1:
            part_sel = st.selectbox(f"Particulars Row {i}", available_items, key=part_key, label_visibility="collapsed", on_change=on_particular_change)
        with c2:
            qty_input = st.number_input(f"Qty Row {i}", min_value=1, step=1, value=1, key=qty_key, label_visibility="collapsed")

        if price_key not in st.session_state:
            st.session_state[price_key] = int(PARTICULARS_MAP.get(part_sel, 0) if part_sel != "--Select Item--" else 0)

        with c3:
            price_input = st.number_input(f"Price Row {i}", min_value=0, step=500, key=price_key, label_visibility="collapsed")

        row_subtotal = float(qty_input * price_input)
        live_total_amount += row_subtotal

        with c4:
            st.markdown(f"<div style='padding-top: 5px;'>Ugx {row_subtotal:,.0f}</div>", unsafe_allow_html=True)
        with c5:
            notes_input = st.text_input(f"Notes Row {i}", key=notes_key, label_visibility="collapsed", placeholder="Add dynamic remarks...")

        if part_sel != "--Select Item--":
            rows_data.append({
                "particular": part_sel,
                "qty": qty_input,
                "unit_price": price_input,
                "subtotal": row_subtotal,
                "cost": COST_MAP.get(part_sel, 0.0) * qty_input,
                "notes": notes_input
            })

    # Show summary running metrics panel
    st.markdown("---")
    st.metric(label="Total Transaction Basket Value", value=f"Ugx {live_total_amount:,.0f}")

    # Row layout alteration elements
    col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 5])
    with col_btn1:
        if st.button("➕ Add Row to Batch"):
            st.session_state.row_count += 1
            st.rerun()
    with col_btn2:
        if st.session_state.row_count > 1:
            if st.button("❌ Remove Last Row"):
                st.session_state.row_count -= 1
                last_idx = st.session_state.row_count
                st.session_state.pop(f"part_{st.session_state.editor_session_id}_{last_idx}", None)
                st.session_state.pop(f"qty_{st.session_state.editor_session_id}_{last_idx}", None)
                st.session_state.pop(f"price_{st.session_state.editor_session_id}_{last_idx}", None)
                st.session_state.pop(f"notes_{st.session_state.editor_session_id}_{last_idx}", None)
                st.rerun()

    # --- 3. LIVE METRICS SUMMARY ---
    is_negative_type = global_tx_type in ["Purchases", "Expenses", "Credit Purchases"]
    display_amount = -live_total_amount if is_negative_type else live_total_amount

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric(label="Total Entries in Batch", value=f"{st.session_state.row_count} rows")
    with col_m2:
        st.metric(label="Total Transaction Amount", value=f"Ugx {int(display_amount):,}")

    # --- 4 & 5. SUBMIT & POST TO POSTGRESQL PIPELINE ---   
    if st.button("Save All Transactions", type="primary"):
        if business_name_sel == "--Select Name--":
            st.error("❌ Please select a valid Business Name at the top dropdown before saving.")
        elif global_tx_type == "--Select Transaction--":
            st.error("❌ Please select a valid Transaction Type at the top dropdown.")
        elif len(rows_data) == 0:
            st.error("❌ Please input data details before attempting to save.")
        else:
            has_errors = False
            summary_rows_markdown = []

            # 1. VALIDATION LOOP
            for idx, row in enumerate(rows_data):
                if row["particular"] == "--Select Item--":
                    st.error(f"❌ Row {idx+1}: Please select a valid product inside the dropdown menu.")
                    has_errors = True
                    break
                if row["unit_price"] <= 0:
                    st.error(f"❌ Row {idx+1}: Price must be greater than 0 Ugx for chosen item: '{row['particular']}'")
                    has_errors = True
                    break

            # 2. WRITE DATA TRANSACTION BLOCK
            if not has_errors:
                with st.spinner("⏳ Safely writing batch to PostgreSQL Database..."):
                    try:
                        with conn.session as session:
                            for row in rows_data:
                                item_part = row["particular"]
                                price = float(row["unit_price"])
                                qty = int(row["qty"])
                                desc = row["notes"].strip()
                                
                                final_price = -abs(price) if is_negative_type else abs(price)
                                amount = float(qty * final_price)

                                # FIXED: Passed the execution dictionary maps directly into the binding engine
                                session.execute(
                                # Fixed Form Insertion Example:
                                session.execute(
                                    text("""
                                        INSERT INTO LNenterprise (
                                        date, business_name, transaction_type, particulars, 
                                        quantity, unit_price, total_amount, customer_name, 
                                        contact_number, notes
                                   ) VALUES (
                                        :date, :business_name, :transaction_type, :particulars, 
                                        :quantity, :unit_price, :total_amount, :customer_name, 
                                        :contact_number, :notes
                                         );
                                    """),
                                    {
                                    "date": tx_date,
                                    "business_name": business_name_sel,
                                    "transaction_type": global_tx_type,
                                    "particulars": item_part,
                                    "quantity": qty,
                                    "unit_price": final_price,
                                    "total_amount": amount,
                                    "customer_name": "Optional",
                                    "contact_number": "",
                                    "notes": desc if desc else "No notes"
                               }
                              )
   
                                summary_rows_markdown.append(
                                    f"| {item_part} | {qty} | Ugx {int(price):,} | Ugx {int(abs(amount)):,} | *None* | {desc if desc else '*No notes*'} |"
                                )
                            session.commit()
                    
                        markdown_table = (
                            f"### 📋 Pauliz P&J Receipt\n"
                            f"**Date:** {tx_date.strftime('%Y-%m-%d')} | **Business Name:** {business_name_sel} | **Type:** {global_tx_type}\n\n"
                            f"| Particulars | Qty | Unit Price | Total Amount | Contact | Description / Notes |\n"
                            f"| :--- | :---: | :--- | :--- | :--- | :--- |\n"
                        ) + "\n".join(summary_rows_markdown) + f"\n\n**Total Amount:** Ugx {int(live_total_amount):,}"
                    
                        st.session_state.last_saved_summary = markdown_table
                    
                        # 🔄 CORRECTED STATE RESET ROUTINE
                        st.session_state.row_count = 1  # Reset row count counter back to 1
                        st.session_state.editor_session_id += 1  # Invalidate widget keys instantly
                    
                        st.success("✅ Transaction successfully logged!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Transaction aborted due to a connection issue: {str(e)}")

            # FIXED: Reference changed from missing rows_to_append to active rows_data list
            elif len(rows_data) == 0 and not has_errors:
                st.error("❌ Please input data details before attempting to save.")

    # --- 6. RECEIPT PREVIEW & DISPLAY (AT THE TOP) ---
    if st.session_state.get("last_saved_summary"):
        st.success("🎉 Last batch transaction successfully saved!")
        with st.expander("📄 View & Copy Last Saved Batch Receipt", expanded=True):
            st.code(st.session_state.last_saved_summary, language="markdown")
            if st.button("Clear Receipt Preview", type="secondary"):
                st.session_state.last_saved_summary = None
                st.rerun()

# --- PAGE 2: Price List ---       
# --- PAGE 2: Price List ---       
elif selection == "Price List":
    st.write(
        '<p style="font-family: Consolas; color: #4e6291; font-size: 15px; font-weight: bold; text-align: Left; margin-bottom: 20px;">Review the Prices and costs of each Item/good</p>',
        unsafe_allow_html=True,
    )
    
    # 1. Pull directly from your native PostgreSQL database connection
    try:
        query_catalog = """
            SELECT 
                particular_name AS "Particulars", 
                price AS "Price (Ugx)", 
                item_cost AS "Item Cost (Ugx)" 
            FROM Particulars_Prices;
        """
        # Fetches real-time catalog directly from Supabase
        df = conn.query(query_catalog, ttl=0)
    except Exception as db_err:
        st.error(f"❌ Failed to fetch price data items from PostgreSQL database: {db_err}")
        df = pd.DataFrame()

    # 2. Render Data
    if not df.empty:
        # Clean up column whitespace from Database strings
        df.columns = df.columns.str.strip()

        # Match exact custom column aliases mapped above
        price_col = "Price (Ugx)"
        cost_col = "Item Cost (Ugx)"

        # Create a clean display copy of the DataFrame
        df_display = df.copy()

        # Safely calculate profit metric difference column
        if price_col in df_display.columns and cost_col in df_display.columns:
            num_price = pd.to_numeric(df_display[price_col], errors='coerce').fillna(0)
            num_cost = pd.to_numeric(df_display[cost_col], errors='coerce').fillna(0)
            df_display["Net Profit (Ugx)"] = num_price - num_cost
        else:
            df_display["Net Profit (Ugx)"] = 0

        # Build dynamic formatting configuration specifically for numeric types
        format_config = {
            price_col: "UGX {:,}",
            cost_col: "UGX {:,}",
            "Net Profit (Ugx)": "UGX {:,}"
        }
        numeric_cols = [price_col, cost_col, "Net Profit (Ugx)"]

        # Apply styling strictly targeted at the numeric subsets
        styled_df = (
            df_display.style
            .format(format_config, na_rep="-") 
            .set_properties(**{
                'text-align': 'right'  # Right-align numeric blocks for clean financial look
            }, subset=numeric_cols)
        )

        # Apply green background gradient map to Net Profit visibility rows
        if "Net Profit (Ugx)" in df_display.columns:
            styled_df = styled_df.background_gradient(subset=["Net Profit (Ugx)"], cmap="YlGn")

        # 7. Render styled interactive dataframe layout
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ No active catalog records or rows found inside the database.")


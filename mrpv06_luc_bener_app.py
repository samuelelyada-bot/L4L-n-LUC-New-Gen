import streamlit as st
import pandas as pd
import numpy as np
import math
from io import BytesIO

# ==========================================
# 1. PAGE CONFIGURATION & HEADER
# ==========================================
st.set_page_config(page_title="MRP System", layout="wide")
st.title("MATERIAL REQUIREMENTS PLANNING SYSTEM (MRP)")

# Interactive explanation strings
l4l_help = "LOT-FOR-LOT (L4L): A lotting technique that orders exactly what is needed for each period, minimizing holding costs to zero but increasing setup frequencies."
luc_help = "LEAST UNIT COST (LUC): A dynamic lotting method that groups successive periods together as long as the average cost per unit decreases."
eoq_help = "ECONOMIC ORDER QUANTITY (EOQ): A fixed lot-sizing model that balances setup costs and holding costs based on average demand to find the optimal order size."

# Render text with interactive tooltips via columns
st.markdown("##### DECISION SUPPORT SYSTEM MODULE")
col_info = st.columns(3)
with col_info[0]:
    st.caption("• L4L Technique", help=l4l_help)
with col_info[1]:
    st.caption("• LUC Technique", help=luc_help)
with col_info[2]:
    st.caption("• EOQ Technique", help=eoq_help)
st.markdown("---")

# ==========================================
# 2. SIDEBAR - CONTROL PARAMETERS
# ==========================================
st.sidebar.header("INPUT PARAMETERS")
setup_cost = st.sidebar.number_input("Ordering / Setup Cost (S)", min_value=0.0, value=100000.0, step=5000.0)
holding_cost = st.sidebar.number_input("Holding Cost (H) (per unit / period)", min_value=0.0, value=2000.0, step=500.0)
initial_inventory = st.sidebar.number_input("Initial Inventory", min_value=0, value=30, step=5)
safety_stock = st.sidebar.number_input("Safety Stock", min_value=0, value=0, step=1)
lead_time = st.sidebar.number_input("Lead Time (Periods)", min_value=0, value=1, step=1)

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def dapatkan_kolom_cocok(columns, targets):
    for col in columns:
        col_clean = str(col).strip().lower().replace("_", "").replace(" ", "")
        if col_clean in targets:
            return col
    return None

def format_lokal_id(number, is_decimal=False):
    """Formats numbers using Indonesian/European standard: Dot for thousands, Comma for decimals"""
    if is_decimal:
        string_num = f"{number:f}".rstrip('0').rstrip('.') if '.' in f"{number:f}" else f"{number}"
        if '.' in string_num:
            integer_part, decimal_part = string_num.split('.')
            integer_part = f"{int(integer_part):,}".replace(",", ".")
            return f"{integer_part},{decimal_part}"
        return f"{int(string_num):,}".replace(",", ".")
    else:
        return f"{int(round(number)):,}".replace(",", ".")

def highlight_luc_warning(row):
    if row['Is_Higher_Internal']:
        return ['background-color: #ffcccc; color: #cc0000; font-weight: bold'] * len(row)
    return [''] * len(row)

def calculate_net_requirements(gross_req, sched_rec, init_inv, ss):
    periods = len(gross_req)
    net_req_list = []
    projected_inv = init_inv
    for k in range(periods):
        nr = max(0, gross_req[k] + ss - (projected_inv + sched_rec[k]))
        net_req_list.append(nr)
        projected_inv = projected_inv + nr + sched_rec[k] - gross_req[k]
    return net_req_list

def generate_poh_and_release(rec_lot, demands, s_receipts, init_inv, lt):
    n = len(demands)
    poh = []
    r_inv = init_inv
    for i in range(n):
        r_inv += s_receipts[i] + rec_lot[i] - demands[i]
        poh.append(r_inv)
    
    rel_lot = [0] * n
    for i in range(n):
        if rec_lot[i] > 0:
            target = i - lt
            if target >= 0:
                rel_lot[target] += rec_lot[i]
            else:
                rel_lot[0] += rec_lot[i] 
    return poh, rel_lot

# ==========================================
# 3. DATA INPUT SECTION
# ==========================================
st.subheader("GROSS REQUIREMENTS AND SCHEDULED RECEIPTS DATA")
input_method = st.radio("Data Input Method:", ["Upload File", "Manual Input", "Template Data"], horizontal=True)

df_kerja = None
if input_method == "Upload File":
    uploaded_file = st.file_uploader("Choose file (xlsx, csv)", type=["csv", "xlsx", "xls"])
    if uploaded_file is not None:
        try:
            df_raw = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            col_periode = dapatkan_kolom_cocok(df_raw.columns, ['periode', 'minggu', 'p', 'period', 'week'])
            col_gr = dapatkan_kolom_cocok(df_raw.columns, ['gr', 'grossrequirement', 'kebutuhankotor', 'grossrequirements'])
            col_sr = dapatkan_kolom_cocok(df_raw.columns, ['sr', 'scheduledreceipt', 'penerimaanterjadwal', 'scheduledreceipts'])
            df_kerja = pd.DataFrame()
            df_kerja['Period'] = df_raw[col_periode].astype(str) if col_periode else [f"P{i+1}" for i in range(len(df_raw))]
            df_kerja['Gross Requirements'] = df_raw[col_gr].fillna(0).astype(int) if col_gr else 0
            df_kerja['Scheduled Receipts'] = df_raw[col_sr].fillna(0).astype(int) if col_sr else 0
        except: st.error("Error reading file format.")
elif input_method == "Manual Input":
    num_periods_input = st.number_input("Number of Periods:", min_value=1, max_value=52, value=8)
    init_data = {'Period': [f"P{i+1}" for i in range(num_periods_input)], 'Gross Requirements': [0]*num_periods_input, 'Scheduled Receipts': [0]*num_periods_input}
    df_kerja = st.data_editor(pd.DataFrame(init_data), use_container_width=True, hide_index=True)
else:
    df_kerja = pd.DataFrame({'Period': [f"P{i}" for i in range(1, 9)], 'Gross Requirements': [30, 40, 20, 70, 40, 10, 30, 60], 'Scheduled Receipts': [0, 10, 0, 0, 20, 0, 0, 0]})

if df_kerja is not None:
    gross_req = df_kerja['Gross Requirements'].tolist()
    sched_rec = df_kerja['Scheduled Receipts'].tolist()
    period_labels = df_kerja['Period'].tolist()
    num_periods = len(gross_req)
    net_req = calculate_net_requirements(gross_req, sched_rec, initial_inventory, safety_stock)

    st.markdown("**PREVIEW INPUT DATA SUMMARY**")
    st.dataframe(pd.DataFrame({'Gross Requirements': gross_req, 'Scheduled Receipts': sched_rec}, index=period_labels).T, use_container_width=True)

    # ==========================================
    # CALCULATION ENGINES
    # ==========================================
    # 1. L4L Engine
    l4l_rec = list(net_req)
    l4l_poh, l4l_rel = generate_poh_and_release(l4l_rec, gross_req, sched_rec, initial_inventory, lead_time)
    total_l4l = (sum(1 for x in l4l_rec if x > 0) * setup_cost) + (sum(l4l_poh) * holding_cost)

    # 2. LUC Engine
    luc_rec = [0] * num_periods
    all_luc_iterations = []
    i = 0
    while i < num_periods:
        if net_req[i] <= 0:
            i += 1
            continue
        best_lot, prev_crit_val = None, None
        for j in range(i, num_periods):
            current_lot = sum(net_req[i:j+1])
            h_cost = sum(net_req[k] * (k - i) * holding_cost for k in range(i, j+1))
            total_c = setup_cost + h_cost
            crit_val = total_c / current_lot if current_lot > 0 else float('inf')
            is_higher = True if (prev_crit_val is not None and crit_val > prev_crit_val) else False
            
            if i == j:
                range_label = f"P{i+1}"
            else:
                range_label = ", ".join([f"P{x}" for x in range(i+1, j+2)])
                
            display_label = f"⚠️ {range_label}" if is_higher else range_label
            all_luc_iterations.append({
                "Period": display_label, 
                "Lot Size": int(current_lot), 
                "Total Cost": format_lokal_id(total_c), 
                "Unit Cost": format_lokal_id(round(crit_val, 2), is_decimal=True),
                "Is_Higher_Internal": is_higher
            })
            
            if not is_higher:
                best_lot = {"Lot Size": current_lot, "End_Idx": j}
                prev_crit_val = crit_val
            else: break
        if best_lot:
            luc_rec[i] = best_lot["Lot Size"]
            i = best_lot["End_Idx"] + 1
        else: i += 1
    luc_poh, luc_rel = generate_poh_and_release(luc_rec, gross_req, sched_rec, initial_inventory, lead_time)
    total_luc = (sum(1 for x in luc_rec if x > 0) * setup_cost) + (sum(luc_poh) * holding_cost)

    # 3. EOQ Engine
    avg_d = np.mean(net_req)
    eoq_size = math.ceil(math.sqrt((2 * avg_d * setup_cost) / holding_cost)) if holding_cost > 0 else 0
    eoq_rec, rem_stok = [0] * num_periods, 0
    for idx in range(num_periods):
        if net_req[idx] > 0:
            if rem_stok < net_req[idx]:
                needed = net_req[idx] - rem_stok
                lots = math.ceil(needed / eoq_size) if eoq_size > 0 else 1
                eoq_rec[idx] = lots * eoq_size
                rem_stok = (eoq_rec[idx] + rem_stok) - net_req[idx]
            else: rem_stok -= net_req[idx]
    eoq_poh, eoq_rel = generate_poh_and_release(eoq_rec, gross_req, sched_rec, initial_inventory, lead_time)
    total_eoq = (sum(1 for x in eoq_rec if x > 0) * setup_cost) + (sum(eoq_poh) * holding_cost)

    # ==========================================
    # 4. METHOD DETAILS (TABS)
    # ==========================================
    st.markdown("---")
    t_l4l, t_luc, t_eoq = st.tabs(["L4L METHOD", "LUC METHOD", "EOQ METHOD"])

    def render_mrp(poh, rec, rel):
        df = pd.DataFrame({'Gross Requirements': gross_req, 'Scheduled Receipts': sched_rec, 'Projected On Hand': poh, 'Net Requirements': net_req, 'Planned Order Receipts': rec, 'Planned Order Releases': rel}, index=period_labels).T
        st.dataframe(df, use_container_width=True)

    with t_l4l:
        st.markdown("**MRP TABLE: LOT-FOR-LOT**")
        render_mrp(l4l_poh, l4l_rec, l4l_rel)
        st.markdown(f"### > **TOTAL COST L4L:** `{format_lokal_id(total_l4l)}`")

    with t_luc:
        st.markdown("**LEAST UNIT COST CALCULATION ITERATIONS**")
        st.write("> **Note:** Red highlighted rows (⚠️) indicate the point where unit cost starts rising, triggering the system to lock the current lot.")
        df_luc_view = pd.DataFrame(all_luc_iterations)
        st.dataframe(
            df_luc_view.style.apply(highlight_luc_warning, axis=1), 
            use_container_width=True, 
            hide_index=True,
            column_order=["Period", "Lot Size", "Total Cost", "Unit Cost"]
        )
        st.markdown("**MRP TABLE: LEAST UNIT COST**")
        render_mrp(luc_poh, luc_rec, luc_rel)
        st.markdown(f"### > **TOTAL COST LUC:** `{format_lokal_id(total_luc)}`")

    with t_eoq:
        st.markdown("**EOQ PARAMETERS**")
        st.info(f"Fixed Lot Size: {eoq_size} units")
        st.markdown("**MRP TABLE: ECONOMIC ORDER QUANTITY**")
        render_mrp(eoq_poh, eoq_rec, eoq_rel)
        st.markdown(f"### > **TOTAL COST EOQ:** `{format_lokal_id(total_eoq)}`")

    # ==========================================
    # 5. PERFORMANCE COMPARISON (MOVED HERE)
    # ==========================================
    st.markdown("---")
    st.subheader("PERFORMANCE COMPARISON OF ALL METHODS")
    biaya_dict = {'L4L': total_l4l, 'LUC': total_luc, 'EOQ': total_eoq}
    best_m = min(biaya_dict, key=biaya_dict.get)
    cols = st.columns(3)
    for i, (name, val) in enumerate(biaya_dict.items()):
        cols[i].metric(f"TOTAL COST {name}", format_lokal_id(val), delta="Optimal Solution" if name == best_m else None)

    # ==========================================
    # 6. EXPORT SECTION
    # ==========================================
    st.markdown("---")
    st.subheader("EXPORT MULTI-METHOD REPORT")
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        pd.DataFrame({'GR': gross_req, 'Net': net_req}, index=period_labels).T.to_excel(writer, sheet_name="Data")
        pd.DataFrame({'L4L': l4l_rec, 'LUC': luc_rec, 'EOQ': eoq_rec}, index=period_labels).T.to_excel(writer, sheet_name="Lotting_Results")
    st.download_button(label="↓ DOWNLOAD EXCEL REPORT", data=excel_buffer.getvalue(), file_name="MRP_Report.xlsx")

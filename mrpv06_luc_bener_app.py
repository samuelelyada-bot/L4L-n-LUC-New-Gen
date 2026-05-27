import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="MRP MCP + LUC Final", layout="wide")
st.title("MRP App – MCP & LUC Final")

# Sidebar parameters
st.sidebar.header("Parameters")
setup_cost = st.sidebar.number_input("Setup Cost per Order (S)", value=500)
holding_cost = st.sidebar.number_input("Holding Cost per Unit (H)", value=5)
initial_inventory = st.sidebar.number_input("Initial Inventory", value=30)
lead_time = st.sidebar.number_input("Lead Time (periods)", value=1)
safety_stock = st.sidebar.number_input("Safety Stock", value=0)

# Create tabs
tabs = st.tabs(["MCP Cumulative", "Least Unit Cost (LUC)"])

# ---------------- MCP Tab ----------------
with tabs[0]:
    st.subheader("MCP Cumulative Iteration")
    uploaded_csv = st.file_uploader("Upload CSV (Period, GR, Scheduled_Receipts) for MCP", type=["csv"], key="mcp_tab")
    if uploaded_csv:
        df_input = pd.read_csv(uploaded_csv)
        periods = len(df_input)
        periods_label = [f"P{i+1}" for i in range(periods)]
        gross_req = df_input['GR'].tolist()
        scheduled_rec = df_input['Scheduled_Receipts'].tolist()

        all_iterations = []
        optimal_combinations = []
        i = 0
        current_inventory = initial_inventory
        prev_cost_per_period = None

        while i < periods:
            best_combo = None
            combos_tried = []

            for j in range(i, periods):
                # NR per periode
                temp_inventory = current_inventory
                nr_list = []
                for k in range(i, j+1):
                    nr = max(0, gross_req[k] + safety_stock - (temp_inventory + scheduled_rec[k]))
                    nr_list.append(nr)
                    temp_inventory += nr + scheduled_rec[k] - gross_req[k]

                net_demand = sum(nr_list)
                planned_receipt = [0]*(j-i+1)
                planned_receipt[0] = net_demand

                # Holding Cost per periode
                temp_inv2 = current_inventory
                cumulative_holding = 0
                for k, nr in zip(range(j-i+1), nr_list):
                    temp_inv2 += planned_receipt[k] + scheduled_rec[i+k] - gross_req[i+k]
                    cumulative_holding += max(temp_inv2,0)
                    temp_inv2 -= gross_req[i+k]

                total_cost = setup_cost + holding_cost * cumulative_holding
                cost_per_period = total_cost / (j-i+1)

                combos_tried.append({
                    "Period Combination": f"{periods_label[i]}-{periods_label[j]}" if i!=j else periods_label[i],
                    "Net Requirement": net_demand,
                    "Lot Size": net_demand,
                    "Total Cost": total_cost,
                    "Cost per Period": cost_per_period
                })

                # Stop iterasi jika Cost per Period naik
                if prev_cost_per_period is not None and cost_per_period > prev_cost_per_period:
                    break
                else:
                    best_combo = (i,j,net_demand,total_cost,cost_per_period)
                    prev_cost_per_period = cost_per_period

            if best_combo is None:
                best_combo = (i,i,nr_list[0], setup_cost + holding_cost*nr_list[0], setup_cost + holding_cost*nr_list[0])

            all_iterations.extend(combos_tried)
            start,end,lot_size,total_cost,cost_per_period = best_combo
            optimal_combinations.append({
                "Period Combination": f"{periods_label[start]}-{periods_label[end]}" if start!=end else periods_label[start],
                "Lot Size": lot_size,
                "Total Cost": total_cost,
                "Cost per Period": cost_per_period
            })

            # Update inventory
            for k in range(start,end+1):
                current_inventory += lot_size if k==start else 0
                current_inventory += scheduled_rec[k] - gross_req[k]

            i = end+1

        st.markdown("### All Iterations Tested (MCP)")
        st.dataframe(pd.DataFrame(all_iterations))
        st.markdown("### Optimal Combination per Step (MCP)")
        st.dataframe(pd.DataFrame(optimal_combinations))

        csv_buffer = BytesIO()
        combined = pd.concat([pd.DataFrame(all_iterations), pd.DataFrame(optimal_combinations)],
                             keys=["All Iterations","Optimal"])
        combined.to_csv(csv_buffer)
        st.download_button("Download MCP CSV", data=csv_buffer,
                           file_name="mcp_final_multitab.csv", mime="text/csv")

# ---------------- LUC Tab ----------------
with tabs[1]:
    st.subheader("Least Unit Cost (LUC) Iteration")
    uploaded_csv = st.file_uploader("Upload CSV (Period, GR, Scheduled_Receipts) for LUC", type=["csv"], key="luc_tab")
    if uploaded_csv:
        df_input = pd.read_csv(uploaded_csv)
        periods = len(df_input)
        periods_label = [f"P{i+1}" for i in range(periods)]
        gross_req = df_input['GR'].tolist()
        scheduled_rec = df_input['Scheduled_Receipts'].tolist()

        all_iterations = []
        optimal_combinations = []
        i = 0
        current_inventory = initial_inventory

        while i < periods:
            best_combo = None
            combos_tried = []

            for j in range(i, periods):
                temp_inventory = current_inventory
                nr_list = []
                for k in range(i,j+1):
                    nr = max(0, gross_req[k] + safety_stock - (temp_inventory + scheduled_rec[k]))
                    nr_list.append(nr)
                    temp_inventory += nr + scheduled_rec[k] - gross_req[k]

                net_demand = sum(nr_list)
                planned_receipt = [0]*(j-i+1)
                planned_receipt[0] = net_demand

                temp_inv2 = current_inventory
                cumulative_holding = 0
                for k, nr in zip(range(j-i+1), nr_list):
                    temp_inv2 += planned_receipt[k] + scheduled_rec[i+k] - gross_req[i+k]
                    cumulative_holding += max(temp_inv2,0)
                    temp_inv2 -= gross_req[i+k]

                total_cost = setup_cost + holding_cost * cumulative_holding
                unit_cost = total_cost / max(net_demand,1)

                combos_tried.append({
                    "Period Combination": f"{periods_label[i]}-{periods_label[j]}" if i!=j else periods_label[i],
                    "Net Requirement": net_demand,
                    "Lot Size": net_demand,
                    "Total Cost": total_cost,
                    "Unit Cost": unit_cost
                })

                if best_combo is not None and unit_cost > best_combo[4]:
                    break
                else:
                    best_combo = (i,j,net_demand,total_cost,unit_cost)

            if best_combo is None:
                best_combo = (i,i,nr_list[0], setup_cost + holding_cost*nr_list[0], setup_cost + holding_cost*nr_list[0])

            all_iterations.extend(combos_tried)
            start,end,lot_size,total_cost,unit_cost = best_combo
            optimal_combinations.append({
                "Period Combination": f"{periods_label[start]}-{periods_label[end]}" if start!=end else periods_label[start],
                "Lot Size": lot_size,
                "Total Cost": total_cost,
                "Unit Cost": unit_cost
            })

            for k in range(start,end+1):
                current_inventory += lot_size if k==start else 0
                current_inventory += scheduled_rec[k] - gross_req[k]

            i = end+1

        st.markdown("### All Iterations Tested (LUC)")
        df_all = pd.DataFrame(all_iterations)
        st.dataframe(df_all)
        st.markdown("### Optimal Combination per Step (LUC)")
        df_optimal = pd.DataFrame(optimal_combinations)
        st.dataframe(df_optimal)

        csv_buffer = BytesIO()
        combined = pd.concat([pd.DataFrame(all_iterations), pd.DataFrame(optimal_combinations)],
                             keys=["All Iterations","Optimal"])
        combined.to_csv(csv_buffer)
        st.download_button("Download LUC CSV", data=csv_buffer,
                           file_name="luc_final_multitab.csv", mime="text/csv")

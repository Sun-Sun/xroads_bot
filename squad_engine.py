import sqlite3
import random
from datetime import datetime
from database import DB_PATH

def generate_final_checklist_squad_logic(setup: dict, active_bosses: list, master_csv_rows: list, assigned_trainees: set):
    """
    Houses the raw mathematical assignment matrix for populating raid lineups.
    Returns:
        tuple: (updated_master_csv_rows, remaining_trainees_count, boss_label, clean_date)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    boss_name = setup["boss"]
    
    # 1. Gather all signups for this target boss run
    cursor.execute(
        "SELECT username, discord_ping, gw2_acc, roles FROM signups WHERE signup_date = ? AND training_name = ?", 
        (setup["day"], boss_name)
    )
    trainees_raw = cursor.fetchall()
    
    lower_leads = set(x.lower() for x in setup["commanders"] + setup["aides"])
    leader_pool = []
    
    # 2. Extract configuration roles for Commanders
    for name in setup["commanders"]:
        cursor.execute("SELECT roles FROM leaders WHERE username = ?", (name,))
        res = cursor.fetchone()
        roles = [r.strip().lower() for r in res[0].split(',') if r.strip()] if res else ["dps"]
        leader_pool.append({"name": name, "roles": roles, "type": "Commander", "assigned_role": "DPS"})
        
    # 3. Extract configuration roles for Aides
    for name in setup["aides"]:
        cursor.execute("SELECT roles FROM leaders WHERE username = ?", (name,))
        res = cursor.fetchone()
        roles = [r.strip().lower() for r in res[0].split(',') if r.strip()] if res else ["dps"]
        leader_pool.append({"name": name, "roles": roles, "type": "Aide", "assigned_role": "DPS"})
        
    trainee_pool = []
    for t_name, t_ping, t_acc, t_roles in trainees_raw:
        if t_name.lower() not in lower_leads and t_name.lower() not in assigned_trainees:
            unique_boss_names = list(set(b["boss_value"] for b in active_bosses))
            if not unique_boss_names:
                unique_boss_names = [boss_name]
                
            placeholders = ", ".join(["?"] * len(unique_boss_names))
            query = f"SELECT COUNT(*) FROM signups WHERE signup_date = ? AND username = ? AND training_name IN ({placeholders})"
            query_params = [setup["day"], t_name] + unique_boss_names
            
            cursor.execute(query, query_params)
            session_boss_count = cursor.fetchone()[0]
            
            parsed_roles = [r.strip().lower() for r in t_roles.split(',') if r.strip()]
            if any(role in parsed_roles for role in ["qheal", "aheal", "quickheal", "alacheal", "qhealtank", "ahealtank"]):
                role_weight = 0
            elif any(role in parsed_roles for role in ["qdps", "adps", "quickdps", "alacdps"]):
                role_weight = 1
            else:
                role_weight = 2
                
            trainee_pool.append({
                "name": t_name, "ping": t_ping, "acc": t_acc, "roles": parsed_roles,
                "roles_raw_str": t_roles, "boss_count": session_boss_count, "role_weight": role_weight
            })
            
    trainee_pool.sort(key=lambda x: (x["boss_count"], x["role_weight"]))
    
    needed_trainees = 10 - len(leader_pool)
    active_trainees = trainee_pool[:min(len(trainee_pool), needed_trainees)]
    
    subgroup_boons = []
    assigned_names = set()
    
    boon_targets = [
        {"type": "qheal", "roles": ["qheal", "quickheal", "qhealtank", "quickhealtank"]},
        {"type": "aheal", "roles": ["aheal", "alacheal", "ahealtank", "alachealtank"]},
        {"type": "qdps", "roles": ["qdps", "quickdps"]},
        {"type": "adps", "roles": ["adps", "alacdps"]}
    ]
    
    random.shuffle(boon_targets)
    
    for target in boon_targets:
        found = False
        for trainee in active_trainees:
            if trainee["name"] not in assigned_names and any(r in trainee["roles"] for r in target["roles"]):
                if "tank" in "".join(trainee["roles"]):
                    trainee["assigned_role"] = "Heal Tank Quickness" if target["type"] == "qheal" else "Heal Tank Alacrity"
                else:
                    trainee["assigned_role"] = "Heal Quickness" if target["type"] == "qheal" else "Heal Alacrity" if target["type"] == "aheal" else "DPS Quickness" if target["type"] == "qdps" else "DPS Alacrity"
                subgroup_boons.append(target["type"])
                assigned_names.add(trainee["name"])
                found = True
                break
        if not found:
            for leader in leader_pool:
                if leader["name"] not in assigned_names and any(r in leader["roles"] for r in target["roles"]):
                    leader["assigned_role"] = "Heal Quickness" if target["type"] == "qheal" else "Heal Alacrity" if target["type"] == "aheal" else "DPS Quickness" if target["type"] == "qdps" else "DPS Alacrity"
                    subgroup_boons.append(target["type"])
                    assigned_names.add(leader["name"])
                    break
                    
    for trainee in active_trainees:
        if trainee["name"] not in assigned_names:
            trainee["assigned_role"] = "DPS"
        assigned_trainees.add(trainee["name"].lower())
        
    for leader in leader_pool:
        if leader["name"] not in assigned_names:
            leader["assigned_role"] = "DPS"
            
    cursor.execute("SELECT COUNT(DISTINCT username) FROM signups WHERE signup_date = ?", (setup["day"],))
    res_count = cursor.fetchone()
    total_unique_trainees = res_count[0] if res_count else 0
    remaining_trainees_count = max(0, total_unique_trainees - len(assigned_trainees))
    
    conn.close()
    
    base_label = "QTP" if setup["boss"] == "Qadim the Peerless" else setup["boss"]
    boss_label = f"{base_label} {setup.get('squad_instance_label', 'Squad 1')}"
    
    try:
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                clean_date = datetime.strptime(setup["day"].strip(), fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
        else:
            clean_date = setup["day"]
    except Exception:
        clean_date = setup["day"]

    for leader in leader_pool:
        final_role = leader.get("assigned_role", "DPS")
        master_csv_rows.append([
            leader["type"], leader["name"], f"@{leader['name']}", 
            clean_date, setup["squad_number"], boss_label, final_role, "-", "all", "all"
        ])
        
    for trainee in active_trainees:
        final_role = trainee.get("assigned_role", "DPS")
        master_csv_rows.append([
            trainee["acc"] if trainee["acc"] else trainee["name"], trainee["name"], trainee["ping"], 
            clean_date, setup["squad_number"], boss_label, final_role, "3", boss_label, trainee["roles_raw_str"]
        ])
        
    total_squad_count = len(leader_pool) + len(active_trainees)
    
    return master_csv_rows, remaining_trainees_count, boss_label, total_squad_count
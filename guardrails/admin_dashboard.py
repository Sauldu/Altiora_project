"""
Dashboard administrateur pour supervision Altiora
Interface de contrôle visuelle et rapports en temps réel
"""

import asyncio
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox
from typing import Dict, Any, List

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Importation des systèmes de contrôle réels
from guardrails.admin_control_system import AdminControlSystem, AdminCommand
from guardrails.ethical_safeguards import EthicalSafeguards, EthicalAlert


class AdminDashboard:
    """
    Interface de dashboard administrateur connectée aux systèmes réels.
    """

    def __init__(self) -> None:
        self.admin_system = AdminControlSystem()
        self.ethical_safeguards = EthicalSafeguards()

        self.root = tk.Tk()
        self.root.title("🎛️ Altiora Admin Dashboard")
        self.root.geometry("1400x900")

        self.stats_labels: Dict[str, ttk.Label] = {}
        self.user_listbox: tk.Listbox
        self.user_info_frame: ttk.LabelFrame
        self.alert_tree: ttk.Treeview
        self.user_filter: ttk.Combobox
        self.period_filter: ttk.Combobox
        self.log_text: tk.Text
        self.notebook: ttk.Notebook

        self.setup_styles()
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.create_overview_tab()
        self.create_user_management_tab()
        self.create_ethical_monitoring_tab()
        self.create_system_logs_tab()
        self.create_emergency_tab()
        self.start_auto_refresh()

    @staticmethod
    def setup_styles() -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#f0f0f0")
        style.configure("TFrame", background="#ffffff")
        style.configure("Critical.TLabel", foreground="red", font=("Arial", 10, "bold"))
        style.configure("Warning.TLabel", foreground="orange", font=("Arial", 10))
        style.configure("Success.TLabel", foreground="green", font=("Arial", 10))

    def create_overview_tab(self) -> None:
        overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(overview_frame, text="Vue d'ensemble")

        header = ttk.Label(overview_frame, text="Tableau de Bord Altiora", font=("Arial", 16, "bold"))
        header.pack(pady=10)

        stats_frame = ttk.Frame(overview_frame)
        stats_frame.pack(pady=20, padx=20)
        for i, stat in enumerate(["Total Users", "Active Alerts", "Pending Changes", "System Status"]):
            frame = ttk.Frame(stats_frame)
            frame.grid(row=0, column=i, padx=20)
            ttk.Label(frame, text=stat, font=("Arial", 12)).pack()
            lbl = ttk.Label(frame, text="N/A", font=("Arial", 14, "bold"))
            lbl.pack()
            self.stats_labels[stat] = lbl

        chart_frame = ttk.Frame(overview_frame)
        chart_frame.pack(pady=20, padx=20, fill="both", expand=True)
        self.create_activity_chart(chart_frame)

    def create_user_management_tab(self) -> None:
        user_frame = ttk.Frame(self.notebook)
        self.notebook.add(user_frame, text="Gestion utilisateurs")

        left = ttk.Frame(user_frame)
        left.pack(side="left", fill="y", padx=10, pady=10)
        ttk.Label(left, text="Utilisateurs", font=("Arial", 12, "bold")).pack()
        self.user_listbox = tk.Listbox(left, width=30, height=25)
        self.user_listbox.pack(pady=10)
        self.user_listbox.bind("<<ListboxSelect>>", self.on_user_select)

        right = ttk.Frame(user_frame)
        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self.user_info_frame = ttk.LabelFrame(right, text="Informations")
        self.user_info_frame.pack(fill="x", pady=10)

        control = ttk.LabelFrame(right, text="Contrôles Admin")
        control.pack(fill="x", pady=10)
        ttk.Button(control, text="Geler Utilisateur", command=lambda: self.execute_user_action("freeze_user")).pack(pady=5, padx=10, fill="x")
        ttk.Button(control, text="Supprimer les données", command=lambda: self.execute_user_action("wipe_user_data")).pack(pady=5, padx=10, fill="x")

    def create_ethical_monitoring_tab(self) -> None:
        ethical_frame = ttk.Frame(self.notebook)
        self.notebook.add(ethical_frame, text="Monitoring éthique")

        alerts_frame = ttk.LabelFrame(ethical_frame, text="Alertes Actives")
        alerts_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.alert_tree = ttk.Treeview(alerts_frame, columns=("User", "Severity", "Details", "Time"), show="headings")
        for col in ("User", "Severity", "Details", "Time"):
            self.alert_tree.heading(col, text=col)
        self.alert_tree.pack(fill="both", expand=True, pady=10)

    def create_system_logs_tab(self) -> None:
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text="Logs système")
        self.log_text = tk.Text(logs_frame, height=30, width=120, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

    def create_emergency_tab(self) -> None:
        emergency_frame = ttk.Frame(self.notebook)
        self.notebook.add(emergency_frame, text="URGENCE")
        ttk.Button(emergency_frame, text="🚨 ACTIVER MODE URGENCE 🚨", command=self.activate_emergency_mode).pack(pady=20)

    def create_activity_chart(self, parent) -> None:
        self.fig, self.ax = plt.subplots(figsize=(12, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def on_user_select(self, _event: tk.Event) -> None:
        selection = self.user_listbox.curselection()
        if selection:
            user_id = self.user_listbox.get(selection[0])
            self.display_user_info(user_id)

    def display_user_info(self, user_id: str) -> None:
        for widget in self.user_info_frame.winfo_children():
            widget.destroy()
        # Remplacer par un appel réel pour obtenir les infos utilisateur
        info = asyncio.run(self.admin_system.get_user_info(user_id))
        for key, value in info.items():
            ttk.Label(self.user_info_frame, text=f"{key}: {value}").pack(anchor="w", padx=10)

    def execute_user_action(self, action: str) -> None:
        selection = self.user_listbox.curselection()
        if not selection:
            messagebox.showwarning("Sélection requise", "Veuillez sélectionner un utilisateur")
            return
        user_id = self.user_listbox.get(selection[0])
        if messagebox.askyesno("Confirmation", f"Confirmer l'action '{action}' sur {user_id} ?"):
            asyncio.run(self.admin_system.execute_admin_command(AdminCommand(
                command_id=f"{action}_{user_id}",
                action=action,
                target_user=user_id
            )))
            messagebox.showinfo("Action effectuée", f"L'action {action} a été exécutée pour {user_id}.")

    def activate_emergency_mode(self) -> None:
        if messagebox.askyesno("URGENCE", "Êtes-vous sûr de vouloir activer le mode urgence ?", icon="warning"):
            asyncio.run(self.admin_system.trigger_emergency(reason="Manual trigger from dashboard"))
            messagebox.showinfo("URGENCE", "Mode urgence activé")

    def start_auto_refresh(self) -> None:
        self.refresh_data()
        self.root.after(5000, self.start_auto_refresh)

    def refresh_data(self) -> None:
        report = self.admin_system.generate_report()
        self.stats_labels["Total Users"].config(text=str(report.get("total_users", 0)))
        self.stats_labels["Active Alerts"].config(text=str(len(self.ethical_safeguards.get_active_alerts())))
        self.stats_labels["System Status"].config(text="NORMAL" if not report.get("emergency_mode") else "URGENCE")
        self.update_user_list()
        self.update_alert_display()
        self.update_logs()
        self.update_activity_chart()

    def update_user_list(self) -> None:
        current_selection = self.user_listbox.curselection()
        self.user_listbox.delete(0, tk.END)
        users = asyncio.run(self.admin_system.list_users())
        for user in users:
            self.user_listbox.insert(tk.END, user)
        if current_selection:
            self.user_listbox.selection_set(current_selection)

    def update_alert_display(self) -> None:
        self.alert_tree.delete(*self.alert_tree.get_children())
        alerts: List[EthicalAlert] = self.ethical_safeguards.get_active_alerts()
        for alert in alerts:
            self.alert_tree.insert("", "end", values=(alert.user_id, alert.severity.name, alert.details, alert.timestamp.strftime("%H:%M:%S")))

    def update_logs(self) -> None:
        logs = self.admin_system.get_system_logs(limit=100)
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert("1.0", "\n".join(logs))
        self.log_text.config(state="disabled")

    def update_activity_chart(self) -> None:
        self.ax.clear()
        # Simuler des données d'activité changeantes
        hours = list(range(24))
        activity = [np.random.randint(50, 200) + h * 5 for h in hours]
        self.ax.plot(hours, activity, marker="o")
        self.ax.set_title("Activité par heure")
        self.ax.set_xlabel("Heure")
        self.ax.set_ylabel("Interactions")
        self.canvas.draw()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    # Note: Pour exécuter ce dashboard, les systèmes sous-jacents doivent être fonctionnels.
    # Cette démo est conceptuelle et peut nécessiter des ajustements.
    dashboard = AdminDashboard()
    dashboard.run()
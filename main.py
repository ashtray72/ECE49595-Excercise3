import tkinter as tk
from tkinter import messagebox, ttk
from tkintermapview import TkinterMapView
from places_client import search_courts, SPORT_QUERIES, PlacesAPIError
from court_manager import CourtManager, SelectionError

MARKER_STYLE = {
    # status      label       circle      outside
    "free":     ("Free",     "green", "darkgreen"),
    "in_use":   ("In Use",   "red",   "darkred"),
    "selected": ("Selected", "gold",  "orange")
}

class interactive_map(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Pickup Game Location Finder")
        self.geometry("900x700")
        
        # State tracking
        self.manager = CourtManager()
        self.current_courts = []
        
        # 1. Top Frame: User Location & Controls
        control_frame = tk.Frame(self, bg="#f0f0f0", height=50)
        control_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(control_frame, text="Your Location:", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        
        self.location_entry = tk.Entry(control_frame, width=25)
        self.location_entry.insert(0, "West Lafayette, IN") # Default
        self.location_entry.pack(side=tk.LEFT, padx=5)

        # Add Sport dropdown menu selection
        tk.Label(control_frame, text="Sport:", font=("Arial", 10, "bold"), bg="#f0f0f0").pack(side=tk.LEFT, padx=5)

        self.sport_var = tk.StringVar(value="Basketball")
        self.sport_dropdown = ttk.Combobox(
            control_frame,
            textvariable=self.sport_var,
            values=list(SPORT_QUERIES.keys()),
            state="readonly",
            width=14
        )
        self.sport_dropdown.pack(side=tk.LEFT, padx=5)
        self.sport_dropdown.bind("<<ComboboxSelected>>", lambda e: self.load_courts())

        search_btn = tk.Button(control_frame, text="Load Courts", command=self.load_courts, bg="#4CAF50", fg="white")
        search_btn.pack(side=tk.LEFT, padx=5)

        # Add button to give up a court
        release_btn = tk.Button(control_frame, text="Release Court", command=self.release_court)
        release_btn.pack(side=tk.LEFT, padx=5)
        
        self.status_label = tk.Label(control_frame, text="Select a court (Max 3 in-use globally)", font=("Arial", 10), bg="#f0f0f0", fg="gray")
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # 2. Center: Interactive Map Widget
        self.map_widget = TkinterMapView(self, width=880, height=600, corner_radius=0)
        self.map_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Set initial position to West Lafayette
        self.map_widget.set_position(40.443333, -86.923611)
        self.map_widget.set_zoom(13)
        
        # Store marker references
        self.markers = []

        self.user_custom_marker = None
        
        # 3. Add a right-click event listener to the map
        self.map_widget.add_right_click_menu_command(
            label="Set as My Location",
            command=self.set_user_loc,
            pass_coords=True
        )


    def load_courts(self):
        """
        Calls Google Places (New) API to find courts for a specified sport near to the user's set marker.
        Places the nearby locations on the map as red pins
        """
        if self.user_custom_marker is None:
            messagebox.showinfo("No location", "Right-click the map and choose 'Set as My Location' first.")
            return

        sport = self.sport_var.get()
        try:
            courts = search_courts(self.user_custom_marker.position, sport)
        except PlacesAPIError as e:
            messagebox.showerror("Search failed", str(e))
            return

        self.current_courts = self.manager.merge_results(courts, sport)
        self.render_courts()


    def render_courts(self):
        """Redraws every court marker using its current status"""
        for m in self.markers:
            m.delete()
        self.markers = []

        for court in self.current_courts:
            label, circle, outside = MARKER_STYLE[self.manager.status(court.id)]
            marker = self.map_widget.set_marker(
                court.lat, court.lon,
                text=f"{court.name} ({label})",
                marker_color_circle=circle,
                marker_color_outside=outside,
                command=lambda m, cid=court.id: self.on_marker_click(cid)
            )
            self.markers.append(marker)

        self.status_label.config(
            text=f"{len(self.current_courts)} courts - "
                 f"{self.manager.in_use_count}/{self.manager.max_in_use} in use"
        )

    def on_marker_click(self, court_id):
        """Handles user selection rules"""
        try:
            court = self.manager.select(court_id)
        except SelectionError as e:
            messagebox.showwarning("Can't select court", str(e))
            return

        self.render_courts()
        messagebox.showinfo("Court Selected", f"You have selected {court.name}")


    def release_court(self):
        if self.manager.selected_court is None:
            messagebox.showinfo("No court", "You don't have a court selected.")
            return
        self.manager.release()
        self.render_courts()

    def set_user_loc(self, coords):
        """   
        Triggered when the user right-clicks the map and selects 'Set as My Location'.
        'coords' is a tuple: (latitude, longitude)
        """       

        lat, lon = coords

        # Remove previous custom marker if it exists
        if self.user_custom_marker:
            self.user_custom_marker.delete()
            
        # Drop a distinct custom marker for the user's location
        self.user_custom_marker = self.map_widget.set_marker(
            lat, lon,
            text="📍 MY LOCATION",
            marker_color_circle="blue", # Optional styling if supported, or rely on text
            marker_color_outside="darkblue"
        )

        # Update the map's center position to the new pin
        #self.map_widget.set_position(lat, lon)
        
        # Update the entry box text with the new coordinates
        self.location_entry.delete(0, tk.END)
        self.location_entry.insert(0, f"{lat:.4f}, {lon:.4f}")
        
        self.status_label.config(text=f"Custom location set to: {lat:.4f}, {lon:.4f}")


if __name__ == "__main__":
    app = interactive_map()
    app.mainloop()
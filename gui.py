import numpy as np
import heapq
import matplotlib.pyplot as plt
import time
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
from datetime import datetime
import os
import random
from matplotlib import colors

from environment_generator import EnvironmentGenerator
from grid_world_env import GridWorldEnv

from path_planning.astar import AStarPlanner
from path_planning.dijkstra import DijkstraPlanner
from path_planning.theta_star import ThetaStarPlanner
from path_planning.bfs import BFSPlanner
from path_planning.greedy_best_first import GreedyBestFirstPlanner
from path_planning.dfs import DFSPlanner
from path_planning.rrt import RRTPlanner
from path_planning.rrt_star import RRTStarPlanner
from path_planning.prm import PRMPlanner

from explanations.lime_explainer import LimeExplainer
from explanations.anchors_explainer import AnchorsExplainer
from explanations.shap_explainer import SHAPExplainer
from explanations.contrastive_explainer import ContrastiveExplainer
from explanations.woe_explainer import WoEExplainer
from explanations.bayesian_surprise_explainer import BayesianSurpriseExplainer
from explanations.pse_explainer import PSEExplainer
from explanations.responsibility_explainer import ResponsibilityExplainer

# Path Planning App
class PathPlanningApp:
    def __init__(self, root):
        self.mosaic = False
        self.json = False

        self.root = root
        self.root.title("Interactive Path Planning Simulator")
        self.root.geometry("900x800")
        style = ttk.Style()
        style.configure("Highlight.TButton", borderwidth=3, relief="solid")
        self.free_selection_enabled = True  # Allows initial click-based setup

        # Path Planning Visualization Type
        self.visualization_mode = "final"  # Options: "step" or "final"
        self.visualization_modes = ["step", "final"]
        self.selected_visualization_mode = tk.StringVar(value=self.visualization_mode)

        # Environment settings
        self.grid_size = 10
        self.num_obstacles = 8
        self.env = None
        self.algorithm_steps = []
        self.current_step = 0
        self.animation_speed = 200  # milliseconds
        self.animation_running = False
        self.setting_start = False
        self.setting_goal = False

        # Interaction settings
        self.selected_obstacle = None
        self.selected_shape_id = None
        
        # Algorithm options
        self.algorithms = ["A*", "Dijkstra", "Theta*", "BFS", "DFS", "Greedy Best-First", "RRT", "RRT*", "PRM"]
        self.selected_algorithm = tk.StringVar(value=self.algorithms[0])
        
        # Explainability options
        self.explainability_methods = ["LIME", "Anchors", "SHAP", "Counterfactual", "Goal-Counterfactual", "Contrastive", "WoE", "Bayesian Surprise", "PSE", "Responsibility"]
        self.selected_explainability = tk.StringVar(value=self.explainability_methods[0])

        # Environment type
        self.environment_types = ["Random", "Feasible", "Infeasible"]
        self.selected_environment_type = tk.StringVar(value=self.environment_types[0])
        
        # Create GUI components
        self.create_gui()
        
        # Generate initial environment
        self.generate_environment()

    def save_environment(self):
        """Save the current environment to a JSON file."""
        from tkinter import filedialog
        
        # Create dictionary with environment data
        env_data = {
            "grid_size": self.grid_size,
            "num_obstacles": self.num_obstacles,
            "obstacle_shapes": self.env.obstacle_shapes,
            "agent_pos": self.env.agent_pos,
            "goal_pos": self.env.goal_pos
        }
        
        # Get filepath from user
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Environment"
        )
        
        if not filepath:  # User cancelled
            return
            
        try:
            with open(filepath, 'w') as f:
                json.dump(env_data, f, indent=2)
            self.status_var.set(f"Environment saved to {filepath}")
        except Exception as e:
            self.status_var.set(f"Error saving environment: {str(e)}")

    def load_environment(self):
        """Load an environment from a JSON file."""
        from tkinter import filedialog
        
        # Get filepath from user
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Environment"
        )
        
        if not filepath:  # User cancelled
            return
            
        try:
            with open(filepath, 'r') as f:
                env_data = json.load(f)
                
            # Update grid size and number of obstacles (if provided)
            self.grid_size = env_data.get("grid_size", self.grid_size)
            self.num_obstacles = env_data.get("num_obstacles", self.num_obstacles)
            
            # Update the UI controls to match loaded values
            self.grid_size_var.set(self.grid_size)
            self.num_obstacles_var.set(self.num_obstacles)
            
            # Create new environment with loaded parameters
            self.env = GridWorldEnv(grid_size=self.grid_size, num_obstacles=self.num_obstacles)
            
            # Load obstacle shapes
            if "obstacle_shapes" in env_data:
                # Convert string keys back to integers
                obstacle_shapes = {int(k): v for k, v in env_data["obstacle_shapes"].items()}
                self.env.obstacle_shapes = obstacle_shapes
                
                # Reconstruct flat obstacles list for quick lookup
                self.env.obstacles = []
                for shape_points in self.env.obstacle_shapes.values():
                    self.env.obstacles.extend(shape_points)
            
            # Load agent and goal positions
            self.env.agent_pos = env_data.get("agent_pos")
            self.env.goal_pos = env_data.get("goal_pos")
            
            # Update UI state based on loaded positions
            self.free_selection_enabled = False
            if self.env.agent_pos and self.env.goal_pos:
                self.start_button.config(state=tk.NORMAL)
                self.status_var.set("Environment loaded. Ready to start planning.")
            elif self.env.agent_pos:
                self.status_var.set("Environment loaded. Click on empty space to set goal position.")
            else:
                self.status_var.set("Environment loaded. Click on empty space to set start position.")
                self.free_selection_enabled = True
            
            # Reset algorithm info
            self.algorithm_steps = []
            self.current_step = 0
            self.animation_running = False
            self.exec_time_var.set("N/A")
            
            # Refresh display
            self.draw_grid()
                
        except Exception as e:
            self.status_var.set(f"Error loading environment: {str(e)}")

    def create_gui(self):
        # Top control panel
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(fill=tk.X)
        
        # Add settings panel for grid size and obstacles
        settings_frame = ttk.LabelFrame(self.root, text="Environment Settings", padding="10")
        settings_frame.pack(fill=tk.X, padx=10, pady=5, before=control_frame)
        
        # Grid size control
        ttk.Label(settings_frame, text="Grid Size:").grid(row=0, column=0, padx=5, pady=5)
        self.grid_size_var = tk.IntVar(value=self.grid_size)
        grid_size_spin = ttk.Spinbox(settings_frame, from_=5, to=20, textvariable=self.grid_size_var, width=5)
        grid_size_spin.grid(row=0, column=1, padx=5, pady=5)
        
        # Obstacles count control
        ttk.Label(settings_frame, text="Obstacles:").grid(row=0, column=2, padx=5, pady=5)
        self.num_obstacles_var = tk.IntVar(value=self.num_obstacles)
        obstacles_spin = ttk.Spinbox(settings_frame, from_=0, to=30, textvariable=self.num_obstacles_var, width=5)
        obstacles_spin.grid(row=0, column=3, padx=5, pady=5)

        # Environment type selector
        ttk.Label(settings_frame, text="Environment Type:").grid(row=0, column=4, padx=5, pady=5)
        env_type_dropdown = ttk.Combobox(
            settings_frame, textvariable=self.selected_environment_type,
            values=self.environment_types, state="readonly", width=10
        )
        env_type_dropdown.grid(row=0, column=5, padx=5, pady=5)

        
        # Apply button
        ttk.Button(settings_frame, text="Apply Settings",
                   command=self.apply_settings).grid(row=0, column=6, padx=5, pady=5)

        # Affordance selector   
        self.selected_affordance = tk.StringVar(value="remove")
        ttk.Label(control_frame, text="Affordance:").grid(row=4, column=0)
        ttk.OptionMenu(control_frame, self.selected_affordance, "remove", "remove", "move", "random").grid(row=4, column=1)
    
        # Save and Load Environment buttons - moved to be after Apply Settings
        ttk.Button(settings_frame, text="Save Environment", 
                  command=self.save_environment).grid(row=0, column=7, padx=5, pady=5)
        ttk.Button(settings_frame, text="Load Environment", 
                  command=self.load_environment).grid(row=0, column=8, padx=5, pady=5)
        
        # Set start and goal buttons
        self.set_start_button = ttk.Button(control_frame, text="Set Start", command=self.enable_set_start)
        self.set_start_button.grid(row=7, column=2, padx=5, pady=5)
        self.set_goal_button = ttk.Button(control_frame, text="Set Goal", command=self.enable_set_goal)
        self.set_goal_button.grid(row=7, column=3, padx=5, pady=5)

        # Button to finalize Plan B selection
        self.done_button = ttk.Button(control_frame, text="Done selecting Plan B", command=lambda: self.finalize_plan_b(self.explainer, self.factual_path))
        self.done_button.grid(row=5, column=0, columnspan=2, pady=5)
        self.done_button.grid_remove()  # Hide initially

        # First row
        ttk.Button(control_frame, text="Generate Environment", 
                command=self.generate_environment).grid(row=0, column=0, padx=5, pady=5)  
        
        ttk.Label(control_frame, text="Algorithm:").grid(row=0, column=1, padx=5, pady=5)
        
        self.algorithm_selector = ttk.Combobox(control_frame, textvariable=self.selected_algorithm, 
                                       values=self.algorithms, state="readonly")
        self.algorithm_selector.grid(row=0, column=2, padx=5, pady=5)
        self.algorithm_selector.bind("<<ComboboxSelected>>", self.on_algorithm_changed)

        # Path Planning Visualization Type
        ttk.Label(control_frame, text="Visualization:").grid(row=0, column=3, padx=5, pady=5)
        self.visualization_selector = ttk.Combobox(
            control_frame, textvariable=self.selected_visualization_mode,
            values=self.visualization_modes, state="readonly", width=8
        )
        self.visualization_selector.grid(row=0, column=4, padx=5, pady=5)
        self.visualization_selector.bind("<<ComboboxSelected>>", self.on_visualization_mode_changed)

        # Add explainability method selection
        ttk.Label(control_frame, text="Explainability:").grid(row=0, column=8, padx=5, pady=5)
        ttk.Combobox(control_frame, textvariable=self.selected_explainability, 
                     values=self.explainability_methods, state="readonly").grid(row=0, column=9, padx=5, pady=5)
        
        # Path Planning button
        self.start_button = ttk.Button(control_frame, text="Start Planning", 
                                       command=self.start_planning, state=tk.DISABLED)
        self.start_button.grid(row=0, column=10, padx=5, pady=5)

        # Explainability button
        explain_button = tk.Button(control_frame, text="Explain", command=self.explain)
        explain_button.grid(row=7, column=0, pady=5)

        # Clear results button
        ttk.Button(control_frame, text="Clear Results", command=self.clear_results).grid(row=7, column=1, padx=5, pady=5)
                
        # Second row - Status and info
        ttk.Label(control_frame, text="Status:").grid(row=1, column=0, pady=5, sticky="w")
        
        self.status_var = tk.StringVar(value="Click on empty space to set start position")
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var)
        self.status_label.grid(row=1, column=1, columnspan=7, pady=5, sticky="w")
        
        # Execution time display
        ttk.Label(control_frame, text="Execution time:").grid(row=2, column=0, pady=5, sticky="w")
        self.exec_time_var = tk.StringVar(value="N/A")
        ttk.Label(control_frame, textvariable=self.exec_time_var).grid(row=2, column=1, columnspan=7, pady=5, sticky="w")
        
        # Canvas for grid display
        self.fig, self.ax = plt.subplots(figsize=(8, 8))
        self.canvas_widget = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Connect mouse click and drag events
        self.canvas_widget.mpl_connect('button_press_event', self.on_grid_click)
        self.canvas_widget.mpl_connect('motion_notify_event', self.on_grid_drag)
        self.canvas_widget.mpl_connect('button_release_event', self.on_grid_release)

    def on_visualization_mode_changed(self, event=None):
        self.visualization_mode = self.selected_visualization_mode.get()
        if self.env.agent_pos and self.env.goal_pos:
            self.start_button.config(state=tk.NORMAL)
        self.status_var.set(f"Visualization mode set to '{self.visualization_mode}'")

    def on_algorithm_changed(self, event=None):
        if self.env.agent_pos and self.env.goal_pos:
            self.start_button.config(state=tk.NORMAL)
            self.status_var.set("Algorithm changed. Ready to start planning.")

    def clear_results(self):
        """Clear path, start and goal points for new selection."""
        if self.env:
            self.env.agent_pos = None
            self.env.goal_pos = None

        self.algorithm_steps = []
        self.current_step = 0
        self.animation_running = False

        self.setting_start = False
        self.setting_goal = False
        self.free_selection_enabled = True  # ← Enable free clicking mode

        self.set_start_button.config(style="TButton")
        self.set_goal_button.config(style="TButton")
        self.start_button.config(state=tk.DISABLED)
        self.exec_time_var.set("N/A")
        self.status_var.set("Cleared. Click on empty space to set start position.")

        self.draw_grid()

    def enable_set_start(self):
        self.setting_start = True
        self.setting_goal = False
        self.set_start_button.config(style="Highlight.TButton")
        self.set_goal_button.config(style="TButton")
        self.status_var.set("Click on grid to set START position.")

    def enable_set_goal(self):
        self.setting_goal = True
        self.setting_start = False
        self.set_goal_button.config(style="Highlight.TButton")
        self.set_start_button.config(style="TButton")
        self.status_var.set("Click on grid to set GOAL position.")

    def apply_settings(self):
        # Update internal settings
        self.grid_size = self.grid_size_var.get()
        self.num_obstacles = self.num_obstacles_var.get()
        
        # Regenerate environment with new settings
        self.generate_environment()
        env_type = self.selected_environment_type.get()
        self.status_var.set(f"Settings applied: Grid size {self.grid_size}, Obstacles {self.num_obstacles}, Type: {env_type}. Click on empty space to set start position.")

    def on_grid_click(self, event):
        if self.animation_running or event.xdata is None or event.ydata is None:
            return
            
        # Convert click coordinates to grid position
        col = int(round(event.xdata))
        row = int(round(event.ydata))
        
        # Check if position is within grid
        if 0 <= row < self.grid_size and 0 <= col < self.grid_size:
            position = [row, col]
            
            # Check if the click is on an obstacle
            is_obstacle = False
            for shape_id, points in self.env.obstacle_shapes.items():
                if position in points:
                    is_obstacle = True
                    # Handle as obstacle click - select for moving
                    self.selected_obstacle = position
                    self.selected_shape_id = shape_id
                    self.status_var.set(f"Selected obstacle at {position}. Drag to move it.")
                    self.draw_grid()  # Redraw to show selection
                    break
            
            # If not an obstacle, handle as empty space click - set points
            if not is_obstacle:
                if self.setting_start:
                    self.env.agent_pos = position
                    self.status_var.set("Start position set.")
                    self.setting_start = False
                    self.set_start_button.config(style="TButton")
                    self.set_goal_button.config(style="TButton")
                    self.free_selection_enabled = False  # Exit free selection
                    self.draw_grid()
                    if self.env.agent_pos and self.env.goal_pos:
                        self.status_var.set("Ready to start planning")
                        self.start_button.config(state=tk.NORMAL)
                    return

                if self.setting_goal:
                    if position == self.env.agent_pos:
                        self.status_var.set("Goal cannot be the same as Start.")
                        return
                    self.env.goal_pos = position
                    self.status_var.set("Goal position set.")
                    self.setting_goal = False
                    self.set_start_button.config(style="TButton")
                    self.set_goal_button.config(style="TButton")
                    self.free_selection_enabled = False
                    self.draw_grid()
                    if self.env.agent_pos and self.env.goal_pos:
                        self.status_var.set("Ready to start planning")
                        self.start_button.config(state=tk.NORMAL)
                    return

                if self.free_selection_enabled:
                    # Set start if not set
                    if self.env.agent_pos is None:
                        self.env.agent_pos = position
                        self.status_var.set("Click on empty space to set goal position")
                        self.draw_grid()
                        if self.env.agent_pos and self.env.goal_pos:
                            self.status_var.set("Ready to start planning")
                            self.start_button.config(state=tk.NORMAL)
                        return
                    # Set goal if not set
                    if self.env.goal_pos is None and position != self.env.agent_pos:
                        self.env.goal_pos = position
                        self.status_var.set("Ready to start planning")
                        self.start_button.config(state=tk.NORMAL)
                        self.free_selection_enabled = False
                        self.draw_grid()
                        if self.env.agent_pos and self.env.goal_pos:
                            self.status_var.set("Ready to start planning")
                            self.start_button.config(state=tk.NORMAL)
                        return

    def on_grid_drag(self, event):
        # Early return checks
        if (self.animation_running or 
            self.selected_obstacle is None or 
            self.selected_shape_id is None or
            event.xdata is None or 
            event.ydata is None):
            return
            
        # Convert coordinates to grid position
        col = int(round(event.xdata))
        row = int(round(event.ydata))
        
        # Calculate movement delta from original selected obstacle position
        old_position = self.selected_obstacle
        delta_row = row - old_position[0]
        delta_col = col - old_position[1]
        
        # Get all points in the current shape
        shape_points = self.env.obstacle_shapes[self.selected_shape_id].copy()
        
        # Calculate new positions for all points in the shape
        new_positions = []
        for point in shape_points:
            new_row = point[0] + delta_row
            new_col = point[1] + delta_col
            new_positions.append([new_row, new_col])
        
        # Check if all new positions are valid
        valid_move = True
        for new_pos in new_positions:
            # Check if position is within grid boundaries
            if not (0 <= new_pos[0] < self.grid_size and 0 <= new_pos[1] < self.grid_size):
                valid_move = False
                break
                
            # Check if not overlapping with other obstacle shapes
            for other_shape_id, other_points in self.env.obstacle_shapes.items():
                if other_shape_id != self.selected_shape_id and new_pos in other_points:
                    valid_move = False
                    break
                    
            # Check if not overlapping with start/goal positions
            if (self.env.agent_pos and new_pos == self.env.agent_pos) or \
            (self.env.goal_pos and new_pos == self.env.goal_pos):
                valid_move = False
                break
            
            # If any check failed, stop validating further positions
            if not valid_move:
                break
        
        # Update positions only if the move is valid
        if valid_move:
            # First, remove all current shape points from obstacles list
            for point in shape_points:
                if point in self.env.obstacles:
                    self.env.obstacles.remove(point)
            
            # Update the shape with new positions
            self.env.obstacle_shapes[self.selected_shape_id] = new_positions
            
            # Add all new positions to obstacles list
            self.env.obstacles.extend(new_positions)
            
            # Update selected obstacle to maintain the same relative position in the shape
            idx = shape_points.index(self.selected_obstacle)
            self.selected_obstacle = new_positions[idx]
            
            # Redraw the grid
            self.draw_grid()
            
            # Set status message
            self.status_var.set(f"Moving obstacle shape #{self.selected_shape_id}")
        else:
            # Inform user that the move is not valid
            self.status_var.set("Cannot move here - out of bounds or obstacle collision")

    def on_grid_release(self, event):
        if self.selected_obstacle is not None:
            # Reset selection after moving
            self.selected_obstacle = None
            self.selected_shape_id = None
            
            # Update status - don't recalculate path automatically
            if self.env.agent_pos is not None and self.env.goal_pos is not None:
                # Enable the start button so user can recalculate when ready
                self.start_button.config(state=tk.NORMAL)
                self.status_var.set("Obstacle moved. Click 'Start Planning' to recalculate path.")
            else:
                if self.env.agent_pos is None:
                    self.status_var.set("Obstacle moved. Click on empty space to set start position.")
                else:
                    self.status_var.set("Obstacle moved. Click on empty space to set goal position.")

    def generate_environment(self):
        # Reset UI state
        self.algorithm_steps = []
        self.current_step = 0
        self.animation_running = False
        self.exec_time_var.set("N/A")
        self.start_button.config(state=tk.DISABLED)
        self.free_selection_enabled = True
        
        # Reset interaction mode
        self.setting_start = False
        self.setting_goal = False
        self.set_start_button.config(style="TButton")
        self.set_goal_button.config(style="TButton")
        
        # Get selected environment type
        env_type = self.selected_environment_type.get()
        self.status_var.set(f"Generating {env_type.lower()} environment...")
        self.root.update()  # Update GUI to show status

        # Create environment generator
        generator = EnvironmentGenerator(grid_size=self.grid_size, num_obstacles=self.num_obstacles)
        
        # Safely extract start and goal if env is initialized
        start = self.env.agent_pos if self.env else None
        goal = self.env.goal_pos if self.env else None
        
        if env_type in ["Feasible", "Infeasible"]:
            if start is None or goal is None:
                self.status_var.set("Please set START and GOAL positions before generating a feasible or infeasible environment.")
                return

            self.env = generator.generate_environment(
                feasible=(env_type == "Feasible"),
                max_attempts=100,
                start=start,
                goal=goal,
                infeasibility_mode="block_path" if env_type == "Infeasible" else None
            )
        else:
            self.env = GridWorldEnv(grid_size=self.grid_size, num_obstacles=self.num_obstacles)
        
        # Check if environment generation was successful
        if self.env is None:
            self.status_var.set(f"Failed to generate {env_type.lower()} environment after multiple attempts. Try different settings.")
            self.env = GridWorldEnv(grid_size=self.grid_size, num_obstacles=self.num_obstacles)
        else:
            # Reset position markers
            if self.env.agent_pos is not None and self.env.goal_pos is not None:
                self.start_button.config(state=tk.NORMAL)
                self.status_var.set("Environment generated. Ready to start planning.") 
            else:
                self.env.agent_pos = None
                self.env.goal_pos = None
                self.status_var.set("Environment ready. Click on empty space to set start position.")
        
        self.draw_grid()

    def draw_grid(self):
        #self.ax.clear() # kicked to out to ensure proper visualization of new environment
        self.fig.clf()
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlim(-0.5, self.grid_size - 0.5)
        self.ax.set_ylim(-0.5, self.grid_size - 0.5)
        self.ax.set_xticks(np.arange(0, self.grid_size, 1))
        self.ax.set_yticks(np.arange(0, self.grid_size, 1))
        self.ax.grid(True, which='both', color='gray', linestyle='-', linewidth=0.5)
        self.ax.set_title("Path Planning Environment")
        
        # Draw shaped obstacles - use different colors for different shapes
        state = self.env.get_state()
        
        # Generate a color map for obstacle shapes
        cmap = plt.colormaps['tab10']
        
        for shape_id, points in state["obstacle_shapes"].items():
            color = cmap(shape_id % 10)  # Use modulo to avoid index errors with many shapes
            
            # Draw filled shape background first
            if points:
                # Add background patches to show connected shapes
                for point in points:
                    # Create a rectangular patch for each cell
                    rect = plt.Rectangle((point[1]-0.5, point[0]-0.5), 1, 1, 
                                        color=color, alpha=0.3)
                    self.ax.add_patch(rect)
            
            # Then draw the obstacle points on top
            for point in points:
                # Highlight selected obstacle
                if self.selected_obstacle == point and self.selected_shape_id == shape_id:
                    self.ax.scatter(point[1], point[0], color='purple', s=120, marker='s')
                else:
                    self.ax.scatter(point[1], point[0], color=color, s=100, marker='s')
            
            # Add a label for the first point of each shape
            if points:
                first_point = points[0]
                self.ax.annotate(f"#{shape_id}", 
                                (first_point[1], first_point[0]),
                                color='white', fontsize=8, 
                                ha='center', va='center')

        # Draw agent if set
        if self.env.agent_pos:
            self.ax.scatter(self.env.agent_pos[1], self.env.agent_pos[0], 
                            color='blue', s=150, marker='o', label="Start")
        
        # Draw goal if set
        if self.env.goal_pos:
            self.ax.scatter(self.env.goal_pos[1], self.env.goal_pos[0], 
                            color='green', s=150, marker='*', label="Goal")
        
        if self.env.agent_pos or self.env.goal_pos:
            self.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=2)
        
        # Invert y-axis to make (0,0) at top-left
        self.ax.invert_yaxis()
            
        self.canvas_widget.draw()

    def start_planning(self):
        if self.env.agent_pos is None or self.env.goal_pos is None:
            self.status_var.set("Please set start and goal positions")
            return
            
        algorithm = self.selected_algorithm.get()
        self.status_var.set(f"Running {algorithm}...")
        self.exec_time_var.set("Running...")
        self.root.update()  # Force update the GUI to show status
        
        self.start_button.config(state=tk.DISABLED)
        
        # Start the algorithm based on selection
        planner_map = {
            "A*": AStarPlanner,
            "Dijkstra": DijkstraPlanner,
            "Theta*": ThetaStarPlanner,
            "BFS": BFSPlanner,
            "DFS": DFSPlanner,
            "Greedy Best-First": GreedyBestFirstPlanner,
            "RRT": RRTPlanner,
            "RRT*": RRTStarPlanner,
            "PRM": PRMPlanner
        }
        planner_class = planner_map.get(self.selected_algorithm.get())
        if planner_class:
            self.visualize_planner(planner_class, name=self.selected_algorithm.get())
        else:
            self.status_var.set("Unknown algorithm selected.")

    def visualize_planner(self, planner_class, name=""):
        self.start_time = time.time()
        planner = planner_class()
        state = self.env.get_state()
        planner.set_environment(
            start=state["agent"],
            goal=state["goal"],
            grid_size=state["grid_size"],
            obstacles=state["obstacles"]
        )
        path, steps = planner.plan(return_steps=True)
        execution_time = time.time() - self.start_time

        self.algorithm_steps = steps
        self.current_step = len(steps) - 1 if steps else 0

        if steps and self.visualization_mode == "final":
            self.draw_step(self.current_step)
        elif steps and self.visualization_mode == "step":
            self.animation_running = True
            self.current_step = 0

            def process_step():
                if self.current_step < len(self.algorithm_steps):
                    self.draw_step(self.current_step)
                    self.current_step += 1
                    self.root.after(self.animation_speed, process_step)
                else:
                    self.animation_running = False

            self.root.after(100, process_step)

        if path:
            self.status_var.set(f"{name}: Path found! Length: {len(path)-1}")
        else:
            self.status_var.set(f"{name}: No path found!")

        self.exec_time_var.set(f"{execution_time:.4f} seconds")
        if self.json:
            self.save_algorithm_steps(execution_time)
        if path and self.mosaic:
            self.generate_mosaic_visualization()
    
    def run_astar_for_analysis(self):
        """Non-visual A* implementation for analysis purposes"""
        state = self.env.get_state()
        planner = AStarPlanner()
        planner.set_environment(
            start=state["agent"],
            goal=state["goal"],
            grid_size=state["grid_size"],
            obstacles=state["obstacles"]
        )
        return planner.plan()

    def draw_step(self, step_idx):
        if step_idx >= len(self.algorithm_steps):
            return
            
        step_data = self.algorithm_steps[step_idx]
        self.current_step = step_idx
        
        # Draw grid
        self.ax.clear()
        self.ax.set_xlim(-0.5, self.grid_size - 0.5)
        self.ax.set_ylim(-0.5, self.grid_size - 0.5)
        self.ax.set_xticks(np.arange(0, self.grid_size, 1))
        self.ax.set_yticks(np.arange(0, self.grid_size, 1))
        self.ax.grid(True)
        
        state = self.env.get_state()
        
        # Draw shaped obstacles with different colors
        cmap = plt.colormaps['tab10']
        for shape_id, points in state["obstacle_shapes"].items():
            color = cmap(shape_id % 10)  # Added modulo to ensure consistency
            
            # Draw filled shape background first
            if points:
                # Add background patches to show connected shapes
                for point in points:
                    # Create a rectangular patch for each cell
                    rect = plt.Rectangle((point[1]-0.5, point[0]-0.5), 1, 1, 
                                        color=color, alpha=0.3)
                    self.ax.add_patch(rect)
            
            # Then draw the obstacle points
            for point in points:
                self.ax.scatter(point[1], point[0], color=color, s=80, marker='s')
        
        # Draw visited nodes
        if "visited" in step_data and step_data["visited"]:
            for node in step_data["visited"]:
                self.ax.scatter(node[1], node[0], color='gray', alpha=0.5, s=80)
        
        # Draw open set
        if "open_set" in step_data and step_data["open_set"]:
            for node in step_data["open_set"]:
                self.ax.scatter(node[1], node[0], color='orange', alpha=0.7, s=80)
        
        # Draw current node
        if "current" in step_data and step_data["current"]:
            current = step_data["current"]
            self.ax.scatter(current[1], current[0], color='red', s=100)
        
        # Draw current path
        if "current_path" in step_data and step_data["current_path"]:
            path = step_data["current_path"]
            path_x = [node[1] for node in path]
            path_y = [node[0] for node in path]
            self.ax.plot(path_x, path_y, 'b-', linewidth=2)
        
        # Draw start and goal
        self.ax.scatter(state["agent"][1], state["agent"][0], 
                        color='blue', s=150, marker='o', label="Start")
        self.ax.scatter(state["goal"][1], state["goal"][0], 
                        color='green', s=150, marker='*', label="Goal")
        
        # Add title with step info
        self.ax.set_title(f"Step {step_idx}: {step_data['description']}")
        
        # Add legend
        self.ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=3)
        
        # Invert y-axis to make (0,0) at top-left
        self.ax.invert_yaxis()
        
        # Update canvas
        self.canvas_widget.draw()

    def save_algorithm_steps(self, execution_time):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Fix filename - replace asterisk with text
        algorithm_name = self.selected_algorithm.get().replace("*", "Star")
        
        # Create output directories if they don't exist
        json_dir = "output_json"
        if not os.path.exists(json_dir):
            os.makedirs(json_dir)
        
        filename = os.path.join(json_dir, f"path_planning_{algorithm_name}_{timestamp}.json")
        
        # Add execution time and final results
        summary = {
            "algorithm": self.selected_algorithm.get(),
            "explainability": self.selected_explainability.get(),
            "grid_size": self.grid_size,
            "start": self.env.agent_pos,
            "goal": self.env.goal_pos,
            "obstacles": self.env.obstacles,  # Save all obstacle positions
            "num_obstacles": len(self.env.obstacles),
            "execution_time": execution_time,
            "total_steps": len(self.algorithm_steps),
            "timestamp": timestamp
        }
        
        # Save path if found
        for step in reversed(self.algorithm_steps):
            if "type" in step and step["type"] == "success" and "current_path" in step:
                summary["path_found"] = True
                summary["path_length"] = len(step["current_path"])
                summary["path"] = step["current_path"]  # Save the actual path
                break
        else:
            summary["path_found"] = False
        
        try:
            # Save to file
            with open(filename, 'w') as f:
                json.dump({
                    "summary": summary,
                    "steps": self.algorithm_steps
                }, f, indent=2)
                
            self.status_var.set(f"Execution completed. Results saved to {filename}")
        except Exception as e:
            self.status_var.set(f"Error saving results: {str(e)}")

    def generate_mosaic_visualization(self):
        """Generate a mosaic visualization of the planning process"""
        
        # Check if we have a successful path
        final_path = None
        for step in reversed(self.algorithm_steps):
            if "type" in step and step["type"] == "success" and "current_path" in step:
                final_path = step["current_path"]
                break
        
        if final_path is None:
            self.status_var.set("No path found, cannot create mosaic visualization")
            return
        
        # Create output directory if it doesn't exist
        images_dir = "output_images"
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        
        # Setup for visualization
        state = self.env.get_state()
        
        # Select key steps for visualization
        # We'll show: 1) Initial state, 2) Several intermediate steps, 3) Final path
        
        # First get all step indices where a path exists
        path_steps = []
        for i, step in enumerate(self.algorithm_steps):
            if "current_path" in step and step["current_path"]:
                path_steps.append(i)
        
        # Determine how many steps to show (max 15)
        num_steps_to_show = min(15, len(path_steps))
        
        # Evenly distribute the steps we'll show
        if num_steps_to_show <= 1:
            step_indices = path_steps  # Just show what we have
        else:
            # Always include the first step with a path and the last (success) step
            # Distribute the remaining evenly
            step_indices = [path_steps[0]]
            if num_steps_to_show > 2:
                # Calculate indices for intermediate steps
                step_size = (len(path_steps) - 1) // (num_steps_to_show - 1)
                for i in range(1, num_steps_to_show - 1):
                    idx = min(i * step_size, len(path_steps) - 1)
                    step_indices.append(path_steps[idx])
            # Add the final step
            if path_steps[-1] not in step_indices:
                step_indices.append(path_steps[-1])
        
        
        # Prepare data for visualization
        paths = []
        titles = []
        
        for idx in step_indices:
            step = self.algorithm_steps[idx]
            if "current_path" in step and step["current_path"]:
                paths.append(step["current_path"])
                
                # Create descriptive title
                if step["type"] == "success":
                    titles.append(f"Final Path (Step {idx})")
                elif idx == step_indices[0]:
                    titles.append(f"Initial Path (Step {idx})")
                else:
                    titles.append(f"Step {idx}")
        
        # Generate a timestamp for the filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(images_dir, f"mosaic_grid_{timestamp}.png")
        
        # Call the visualization function with all steps
        self.visualize_mosaic(state, paths, self.grid_size, titles, save_path=filename)
        self.status_var.set(f"Mosaic visualization saved as {filename}")
        
        # # Also save individual visualizations for each important step
        # for i, (path, title) in enumerate(zip(paths, titles)):
        #     step_filename = os.path.join(images_dir, f"step_{timestamp}_{i:02d}.png")
        #     self.save_single_step_visualization(state, path, self.grid_size, title, save_path=step_filename)

    def save_single_step_visualization(self, environment, path, grid_size, title, save_path):
        """Save visualization of a single step"""
        fig, ax = plt.subplots(figsize=(8, 8))
        
        ax.set_xlim(-0.5, grid_size - 0.5)
        ax.set_ylim(-0.5, grid_size - 0.5)
        ax.set_aspect('equal')
        ax.grid(True, which='both', color='gray', linestyle='-', linewidth=0.5)
        ax.set_title(title)
        
        cmap = plt.colormaps['tab10']
        for shape_id, points in environment["obstacle_shapes"].items():
            color = cmap(shape_id % 10)
            for obs in points:
                # Add label only for the first point of the first shape
                label = "Obstacle" if shape_id == 0 and obs == points[0] else ""
                ax.scatter(obs[1], obs[0], color=color, s=100, marker='s', label=label)
        
        # Plot agent
        ax.scatter(environment["agent"][1], environment["agent"][0], color='blue', s=150, marker='o', label="Start")
        
        # Plot goal
        ax.scatter(environment["goal"][1], environment["goal"][0], color='green', s=150, marker='*', label="Goal")
        
        # Plot path
        if path:
            path_x = [pos[1] for pos in path]
            path_y = [pos[0] for pos in path]
            ax.plot(path_x, path_y, color='orange', linewidth=2, label=f"Path (length: {len(path)-1})")
        
        # Add legend
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=3)
        
        # Invert y-axis to match the main visualization
        ax.invert_yaxis()
        
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close(fig)

    def visualize_mosaic(self, environment, paths, grid_size, titles=None, save_path="mosaic_grid.png"):
        """Create a mosaic visualization with different paths"""
        num_paths = len(paths)
        
        # Determine grid layout - try to make it somewhat square
        cols = min(5, num_paths)
        rows = int(np.ceil(num_paths / cols))
        
        fig, axes = plt.subplots(rows, cols, figsize=(cols * 3, rows * 3))
        
        # Handle case with single plot
        if rows == 1 and cols == 1:
            axes = np.array([axes])
        
        axes = axes.flatten()
        
        for idx in range(num_paths):
            ax = axes[idx]
            ax.set_xlim(-0.5, grid_size - 0.5)
            ax.set_ylim(-0.5, grid_size - 0.5)
            ax.set_aspect('equal')
            ax.set_xticks(np.arange(0, grid_size, 1))
            ax.set_yticks(np.arange(0, grid_size, 1))
            ax.set_xticklabels([])
            ax.set_yticklabels([])
            ax.grid(True, which='both', color='gray', linestyle='-', linewidth=0.5)
            
            # Set title
            if titles and idx < len(titles):
                ax.set_title(titles[idx])
            else:
                ax.set_title(f"Path {idx+1}")
            
            # Plot obstacles with shape colors
            cmap = plt.colormaps['tab10']
            for shape_id, points in environment["obstacle_shapes"].items():
                color = cmap(shape_id % 10)  # Added modulo for consistency
                for obs in points:
                    ax.scatter(obs[1], obs[0], color=color, s=80, marker='s')
            
            # Plot agent
            ax.scatter(environment["agent"][1], environment["agent"][0], color='blue', s=100, marker='o')
            
            # Plot goal
            ax.scatter(environment["goal"][1], environment["goal"][0], color='green', s=100, marker='*')
            
            # Plot path
            path = paths[idx]
            if path and path != [-1]:
                path_x = [pos[1] for pos in path]
                path_y = [pos[0] for pos in path]
                ax.plot(path_x, path_y, color='orange', linewidth=1.5)
            
            # Invert y-axis to match the main visualization
            ax.invert_yaxis()
        
        # Hide unused subplots
        for idx in range(num_paths, len(axes)):
            axes[idx].axis('off')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

    #########################################################################################
    # EXPLANATION METHODS    

    def explain(self):
        """Generate explanations based on selected explanation method"""
        if self.env.agent_pos is None or self.env.goal_pos is None:
            self.status_var.set("Please set start and goal positions first")
            return
            
        self.status_var.set("Generating explanations... Please wait.")
        self.root.update()
        
        # Get the selected explanation method
        explanation_method = self.selected_explainability.get()
        
        # Create the appropriate planner
        planner_map = {
            "A*": AStarPlanner,
            "Dijkstra": DijkstraPlanner,
            "Theta*": ThetaStarPlanner,
            "BFS": BFSPlanner,
            "DFS": DFSPlanner,
            "Greedy Best-First": GreedyBestFirstPlanner,
            "RRT": RRTPlanner,
            "RRT*": RRTStarPlanner,
            "PRM": PRMPlanner
        }
        planner_class = planner_map.get(self.selected_algorithm.get(), AStarPlanner)
        planner = planner_class()
        
        # Set up the planner
        planner.set_environment(
            start=self.env.agent_pos,
            goal=self.env.goal_pos,
            grid_size=self.grid_size,
            obstacles=self.env.obstacles
        )
        
        # Create and run the appropriate explainer
        if explanation_method == "LIME":
            self.explain_with_lime(planner)
        elif explanation_method == "Anchors":
            self.explain_with_anchors(planner)
        elif explanation_method == "SHAP":
            self.explain_with_shap(planner)
        elif explanation_method == 'Contrastive':
            self.explain_with_contrastive(planner)
        elif explanation_method == 'Counterfactual':
            self.explain_with_counterfactual(planner)
        elif explanation_method == 'Goal-Counterfactual':
            self.explain_with_goal_counterfactual(planner)
        elif explanation_method == "WoE":
            self.explain_with_woe(planner)
        elif explanation_method == "Bayesian Surprise":
            self.explain_with_bayesian_surprise(planner)
        elif explanation_method == "PSE":
            self.explain_with_pse(planner)
        elif explanation_method == "Responsibility":
            self.explain_with_responsibility(planner)
        else:
            self.status_var.set(f"Unknown explanation method: {explanation_method}")

    def explain_with_lime(self, planner):
        """Generate LIME explanations"""
        # Create explainer
        explainer = LimeExplainer()
        explainer.set_environment(self.env, planner)
        
        # Callback for progress updates
        def update_progress(current, total):
            self.status_var.set(f"Generating LIME explanation: {current+1}/{total}")
            self.root.update()
        
        # Generate explanations
        affordance_mode = self.selected_affordance.get()
        importance = explainer.explain(
            num_samples=len(self.env.obstacle_shapes.keys()) + 10,
            callback=update_progress,
            strategy="remove_each_obstacle_once", # "remove_each_obstacle_once", "random", "full_combinations"
            perturbation_mode=affordance_mode  # "move" or "remove" or "random"
        )
        
        if len(importance) == 0:
            self.status_var.set("No obstacles to explain.")
            return
        
        # Create a heatmap representation
        obstacle_keys = list(self.env.obstacle_shapes.keys())
        grid = np.zeros((self.grid_size, self.grid_size))
        
        # Map importance values to the grid
        for idx, shape_id in enumerate(obstacle_keys):
            imp_value = importance[idx]
            for pos in self.env.obstacle_shapes[shape_id]:
                x, y = pos
                if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
                    grid[x, y] = imp_value
        
        # Create visualization
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Use diverging colormap for positive/negative influences
        cmap = plt.cm.coolwarm
        
        # Handle potential extreme values
        grid_finite = np.nan_to_num(grid, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Calculate bounds safely
        if np.all(grid_finite == 0):
            # All values are zero or NaN/inf (replaced with 0)
            vmin, vmax = -1, 1  # Use default range
        else:
            # Normalize around zero with a safe range
            max_abs = max(abs(np.min(grid_finite)), abs(np.max(grid_finite)))
            # Add a small buffer to avoid exactly zero range
            max_abs = max(max_abs, 0.1)
            vmin, vmax = -max_abs, max_abs
        
        # Create a safer normalization
        norm = colors.TwoSlopeNorm(vmin=vmin, vcenter=0, vmax=vmax)
        
        # Create heatmap with explicit min/max to avoid hover errors
        heatmap = ax.imshow(grid_finite, cmap=cmap, norm=norm, interpolation='nearest')
        
        # Disable hover tooltips that cause problems
        for artist in ax.get_children():
            artist.set_picker(None)
        
        # Draw grid lines for clarity
        ax.set_xticks(np.arange(-0.5, self.grid_size, 1), minor=True)
        ax.set_yticks(np.arange(-0.5, self.grid_size, 1), minor=True)
        ax.grid(which='minor', color='gray', linestyle='-', linewidth=0.5)
        ax.tick_params(which='both', bottom=False, left=False, labelbottom=False, labelleft=False)
        
        # Mark start and goal positions
        if self.env.agent_pos:
            ax.scatter(self.env.agent_pos[1], self.env.agent_pos[0], 
                    color='blue', s=150, marker='o', label='Start')
        if self.env.goal_pos:
            ax.scatter(self.env.goal_pos[1], self.env.goal_pos[0], 
                    color='green', s=150, marker='*', label='Goal')
        
        # Add colorbar
        cbar = plt.colorbar(heatmap, ax=ax)
        cbar.set_label('Obstacle Importance')
        
        # Add title
        plt.title('LIME: Obstacle Importance for Path Planning\n'
                'Blue: Removal makes path worse (critical obstacle)\n'
                'Red: Removal helps path (obstructive obstacle)')
        
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=2)
        
        # Save explanation
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        images_dir = "output_images"
        if not os.path.exists(images_dir):
            os.makedirs(images_dir)
        
        filepath = os.path.join(images_dir, f"lime_explanation_{timestamp}.png")
        plt.savefig(filepath, bbox_inches='tight', dpi=150)
        
        # Also display it
        plt.show()
        
        self.status_var.set(f"LIME explanation generated and saved to {filepath}")

    def explain_with_anchors(self, planner):
        """Generate Anchors explanations"""
        explainer = AnchorsExplainer()
        explainer.set_environment(self.env, planner)
        
        # Create UI for detection mode choice
        top = tk.Toplevel(self.root)
        top.title("Anchors Explanation Options")
        top.geometry("400x200")
        
        # Create variables for user choices
        detect_changes_var = tk.BooleanVar(value=False)
        num_samples_var = tk.IntVar(value=20)
        affordance_mode = self.selected_affordance.get()
        
        # Create option selection frame
        frame = ttk.Frame(top, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Explanation target options
        ttk.Label(frame, text="Find rules where:").grid(row=0, column=0, sticky="w", pady=10)
        ttk.Radiobutton(frame, text="Path remains stable", variable=detect_changes_var, 
                        value=False).grid(row=1, column=0, sticky="w", padx=20)
        ttk.Radiobutton(frame, text="Path changes significantly", variable=detect_changes_var, 
                        value=True).grid(row=2, column=0, sticky="w", padx=20)
        
        # Number of samples slider
        ttk.Label(frame, text="Number of samples:").grid(row=3, column=0, sticky="w", pady=10)
        ttk.Scale(frame, from_=10, to=200, variable=num_samples_var, 
                orient=tk.HORIZONTAL).grid(row=4, column=0, sticky="ew")
        ttk.Label(frame, textvariable=num_samples_var).grid(row=4, column=1)
        
        # Run button
        ttk.Button(frame, text="Generate Explanation", 
                command=lambda: run_explanation()).grid(row=5, column=0, pady=15)
        
        def run_explanation():
            # Close dialog
            top.destroy()
            
            # Get user selections
            detect_changes = detect_changes_var.get()
            num_samples = num_samples_var.get()
            
            # Update status
            self.status_var.set(f"Generating Anchors explanation: finding rules where paths {'change' if detect_changes else 'remain stable'}...")
            self.root.update()
            
            # Callback for progress updates
            def update_progress(current, total):
                self.status_var.set(f"Generating Anchors explanation: {current+1}/{total}")
                self.root.update()

            # set smaller precision for path changes
            if detect_changes:
                precision_threshold = 0.1
            else:
                precision_threshold = 0.9
            
            # Generate explanations
            anchors = explainer.explain(
                num_samples=num_samples,
                precision_threshold=precision_threshold,
                min_coverage=0.1,
                callback=update_progress,
                detect_changes=detect_changes,
                perturbation_mode=affordance_mode
            )
            
            if not anchors:
                self.status_var.set(f"No meaningful anchors found for {'path changes' if detect_changes else 'path stability'}.")
                return
            
            # Visualize the anchors
            fig = explainer.visualize(anchors)
            
            if fig:
                # Save explanation
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                images_dir = "output_images"
                if not os.path.exists(images_dir):
                    os.makedirs(images_dir)
                
                path_type = "changing" if detect_changes else "stable"
                filepath = os.path.join(images_dir, f"anchors_explanation_{path_type}_{timestamp}.png")
                fig.savefig(filepath, bbox_inches='tight', dpi=150)
                
                # Also display it
                plt.show()
                
                self.status_var.set(f"Anchors explanation for {path_type} paths generated and saved to {filepath}")
            else:
                self.status_var.set("Could not generate Anchors visualization.")

    def explain_with_shap(self, planner):
        """Generate SHAP explanations"""
        # Create explainer
        explainer = SHAPExplainer()
        explainer.set_environment(self.env, planner)
        
        # Callback for progress updates
        def update_progress(current, total):
            self.status_var.set(f"Generating SHAP explanation: {current+1}/{total}")
            self.root.update()
        
        # Generate explanations
        affordance_mode = self.selected_affordance.get()
        shap_values = explainer.explain(
            num_samples=150,  # Less samples for faster computation
            callback=update_progress,
            perturbation_mode=affordance_mode  # "move" or "remove" or "random"
        )
        
        if not shap_values:
            self.status_var.set("No meaningful SHAP values found.")
            return
        
        # Visualize the SHAP values
        fig = explainer.visualize(shap_values)
        
        if fig:
            # Save explanation
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            images_dir = "output_images"
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            
            filepath = os.path.join(images_dir, f"shap_explanation_{timestamp}.png")
            fig.savefig(filepath, bbox_inches='tight', dpi=150)
            
            # Also display it
            plt.show()
            
            self.status_var.set(f"SHAP explanation generated and saved to {filepath}")
        else:
            self.status_var.set("Could not generate SHAP visualization.")

    def explain_with_counterfactual(self, planner):
        explainer = CounterfactualExplainer()
        explainer.set_environment(self.env, planner)
        affordance_mode = self.selected_affordance.get()
        counterfactuals = explainer.explain(max_subset_size=2,
                                            perturbation_mode=affordance_mode  # "move" or "remove" or "random"
                                            )

        fig = explainer.visualize(counterfactuals)

        if fig:
            # Save explanation
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            images_dir = "output_images"
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            
            filepath = os.path.join(images_dir, f"counterfactual_explanation_{timestamp}.png")
            fig.savefig(filepath, bbox_inches='tight', dpi=150)
            
            # Also display it
            plt.show()
            
            self.status_var.set(f"Counterfactual explanation generated and saved to {filepath}")
        else:
            self.status_var.set("Could not generate Counterfactual visualization.")

    def explain_with_contrastive(self, planner):
        self.explainer = ContrastiveExplainer()
        self.explainer.set_environment(self.env, planner)

        self.factual_path = planner.plan()
        if not self.factual_path:
            self.status_var.set("Factual path not found. Cannot explain.")
            return

        self.status_var.set("Click to define an alternative path (Plan B). Press 'Done' when finished.")
        self.alt_path = []
        self.plan_b_connection_id = self.canvas_widget.mpl_connect('button_press_event', self.collect_alt_path_click)
        self.done_button.grid()  # Show button

    def finalize_plan_b(self, explainer, factual_path):
        if not self.alt_path:
            self.status_var.set("No alternative path selected.")
            return

        self.canvas_widget.mpl_disconnect(self.plan_b_connection_id)
        self.done_button.grid_remove()

        use_minimal = tk.messagebox.askyesno("Minimal Explanation", "Do you want to compute a minimal explanation?")
        result = explainer.explain(factual_path, self.alt_path, minimal=use_minimal)
        fig = explainer.visualize(result)

        if fig:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            images_dir = "output_images"
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            filepath = os.path.join(images_dir, f"contrastive_explanation_{timestamp}.png")
            fig.savefig(filepath, bbox_inches='tight', dpi=150)
            plt.show()
            self.status_var.set(f"Contrastive explanation saved to {filepath}")


    def collect_alt_path_click(self, event):
        if event.xdata is None or event.ydata is None:
            return
        row = int(round(event.ydata))
        col = int(round(event.xdata))
        if 0 <= row < self.grid_size and 0 <= col < self.grid_size:
            self.alt_path.append([row, col])
            self.status_var.set(f"Added point to Plan B: ({row}, {col})")
            self.draw_grid()
            self.ax.plot([p[1] for p in self.alt_path], [p[0] for p in self.alt_path], color='purple', linewidth=2)
            self.canvas_widget.draw()

    def explain_with_goal_counterfactual(self, planner):
        explainer = GoalCounterfactualExplainer()
        explainer.set_environment(self.env, planner)
        counterfactuals = explainer.explain(max_goals=5)

        fig = explainer.visualize(counterfactuals)
        if fig:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            images_dir = "output_images"
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)

            filepath = os.path.join(images_dir, f"goal_cf_explanation_{timestamp}.png")
            fig.savefig(filepath, bbox_inches='tight', dpi=150)
            plt.show()
            self.status_var.set(f"Goal-Counterfactual explanation saved to {filepath}")
        else:
            self.status_var.set("No valid goal counterfactuals could be generated.")

    def explain_with_woe(self):
        self.explainer = WoEExplainer()
        self.explainer.set_environment(self.env, self.planner)

        self.factual_path = self.planner.plan()
        if not self.factual_path:
            self.status_var.set("Factual path not found. Cannot explain.")
            return

        self.status_var.set("Click to define an alternative path (Plan B). Press 'Done' when finished.")
        self.alt_path = []
        self.plan_b_connection_id = self.canvas_widget.mpl_connect('button_press_event', self.collect_alt_path_click_woe)
        self.done_button.configure(command=lambda: self.finalize_plan_b_woe(self.explainer, self.factual_path))
        self.done_button.pack(side='left', padx=5)

    def collect_alt_path_click_woe(self, event):
        if event.xdata is None or event.ydata is None:
            return
        row = int(round(event.ydata))
        col = int(round(event.xdata))
        if 0 <= row < self.grid_size and 0 <= col < self.grid_size:
            self.alt_path.append([row, col])
            self.status_var.set(f"Added point to Plan B: ({row}, {col})")
            self.draw_grid()
            self.ax.plot([p[1] for p in self.alt_path], [p[0] for p in self.alt_path], color='purple', linewidth=2)
            self.canvas_widget.draw()

    def finalize_plan_b_woe(self, explainer, factual_path):
        if not self.alt_path:
            self.status_var.set("No alternative path selected.")
            return

        self.canvas_widget.mpl_disconnect(self.plan_b_connection_id)
        self.done_button.pack_forget()

        trials = tk.simpledialog.askinteger("Trials", "How many trials per obstacle?", initialvalue=10, minvalue=1)
        if not trials:
            trials = 10

        result = explainer.explain(factual_path, self.alt_path, trials=trials)
        fig = explainer.visualize(result)

        if fig:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            images_dir = "output_images"
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            filepath = os.path.join(images_dir, f"woe_explanation_{timestamp}.png")
            fig.savefig(filepath, bbox_inches='tight', dpi=150)
            plt.show()
            self.status_var.set(f"WoE explanation saved to {filepath}")

    def explain_with_bayesian_surprise(self, planner):
        explainer = BayesianSurpriseExplainer()
        explainer.set_environment(self.env, planner)

        surprise_value = explainer.explain(perturbation_mode=self.selected_affordance.get(),
                                        num_samples=30)

        posterior_probs = np.ones(30) / 30  # For visualization
        fig = explainer.visualize(posterior_probs)

        if fig:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            images_dir = "output_images"
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)

            filepath = os.path.join(images_dir, f"bayesian_surprise_{timestamp}.png")
            fig.savefig(filepath, bbox_inches='tight', dpi=150)
            plt.show()
            self.status_var.set(f"Bayesian Surprise: {surprise_value:.4f} | Saved to {filepath}")
        else:
            self.status_var.set(f"Bayesian Surprise: {surprise_value:.4f}")

    def explain_with_pse(self, planner):
        explainer = PSEExplainer()
        explainer.set_environment(self.env, planner)
        result = explainer.explain(threshold=0.9)

        fig = explainer.visualize(result)
        if fig:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            images_dir = "output_images"
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            filepath = os.path.join(images_dir, f"pse_explanation_{timestamp}.png")
            fig.savefig(filepath, bbox_inches='tight', dpi=150)
            plt.show()
            self.status_var.set(f"PSE explanation saved to {filepath}")
        else:
            self.status_var.set("Could not generate PSE explanation.")

    def explain_with_responsibility(self, planner):
        explainer = ResponsibilityExplainer()
        explainer.set_environment(self.env, planner)
        result = explainer.explain(max_changes=2)

        fig = explainer.visualize(result)
        if fig:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            images_dir = "output_images"
            if not os.path.exists(images_dir):
                os.makedirs(images_dir)
            filepath = os.path.join(images_dir, f"responsibility_explanation_{timestamp}.png")
            fig.savefig(filepath, bbox_inches='tight', dpi=150)
            plt.show()
            self.status_var.set(f"Responsibility explanation saved to {filepath}")
        else:
            self.status_var.set("Could not generate Responsibility explanation.")

# Run the application
if __name__ == "__main__":
    root = tk.Tk()
    app = PathPlanningApp(root)
    root.mainloop()
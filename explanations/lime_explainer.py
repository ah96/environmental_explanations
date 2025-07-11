import numpy as np
import random
from sklearn.linear_model import Ridge

class LimeExplainer:
    """
    LIME-based explanation for path planning.
    Explains the importance of obstacles by removing them and observing path changes.
    """
    
    def __init__(self):
        """Initialize the LIME explainer"""
        self.grid_size = None
        self.planner = None
        self.env = None
    
    def set_environment(self, env, planner):
        """
        Set the environment and planner to be explained
        
        Args:
            env: Environment object with grid_size and obstacles
            planner: Path planner that has a plan() method
        """
        self.env = env.clone()
        self.planner = planner
        self.grid_size = env.grid_size
    
    def explain(self, num_samples=100, callback=None, strategy="remove_each_obstacle_once", perturbation_mode="remove"):
        """
        Generate LIME-based explanations for the path planning problem
        
        Args:
            num_samples: Number of perturbation samples to generate
            callback: Optional callback function to update progress
            
        Returns:
            importance: Array of importance values for each obstacle shape
        """
        # Make a deep copy of the original environment state to restore later
        original_env_state = self.env.clone()
        
        # Get obstacle keys and store them to maintain consistency
        obstacle_keys = list(self.env.obstacle_shapes.keys())
        num_obstacles = len(obstacle_keys)
        
        if num_obstacles == 0:
            return []
        
        combinations = []
        random_combinations = []
        # Generate perturbation combinations based on strategy
        if strategy == "remove_each_obstacle_once":
            combinations = self.env.generate_perturbation_combinations("remove_each_obstacle_once")
        
            # Also generate some random combinations (but limit total to avoid long processing)
            max_random = min(20, num_samples - len(combinations))
            for _ in range(max_random):
                combo = [random.randint(0, 1) for _ in range(num_obstacles)]
                random_combinations.append(combo)

        elif strategy == "random":
            combinations = []
            for _ in range(num_samples):
                combo = [random.randint(0, 1) for _ in range(num_obstacles)]
                combinations.append(combo)

        elif strategy == "full_combinations":
            combinations = self.env.generate_perturbation_combinations("full_combinations")
        
        # Combine all the combinations
        all_combinations = combinations + random_combinations
        
        X = []  # Perturbations (binary mask per sample)
        y = []  # Path costs per sample
        
        # Store original obstacles to restore after each perturbation
        original_obstacles = self.env.obstacles.copy()
        original_obstacle_shapes = {k: v.copy() for k, v in self.env.obstacle_shapes.items()}
        
        # Process each combination
        total_combinations = len(all_combinations)
        
        for i, combination in enumerate(all_combinations):
            # Update progress if callback provided
            if callback:
                callback(i, total_combinations)
            
            # Ensure combination length matches original obstacle count
            if len(combination) != num_obstacles:
                if len(combination) > num_obstacles:
                    # Trim combination if too long
                    combination = combination[:num_obstacles]
                else:
                    # Extend combination if too short
                    combination = combination + [1] * (num_obstacles - len(combination))
            
            # Reset environment to original state before each perturbation
            self.env.obstacles = original_obstacles.copy()
            self.env.obstacle_shapes = {k: v.copy() for k, v in original_obstacle_shapes.items()}
            
            # Apply perturbation using the fixed-length combination
            original_state, _ = self.env.generate_perturbation(
                combination=combination,
                mode=perturbation_mode
            )
            
            # Run path planning
            path = self.planner.plan(
                self.env.agent_pos, 
                self.env.goal_pos, 
                self.env.obstacles
            )
            
            # Measure outcome: path length or failure penalty
            if path:
                path_length = len(path)
                success = True
            else:
                path_length = self.grid_size * 2  # Penalty for no path
                success = False
            
            # Record results (ensuring consistent length)
            X.append(combination)
            y.append(path_length)
            
            # Restore environment to original state
            self.env.restore_from_perturbation(original_state)
        
        # Convert to numpy arrays
        X = np.array(X, dtype=np.int32)  # Specify dtype to ensure consistent types
        y = np.array(y)
        
        # Fit a Ridge regression model to explain obstacle importance
        explainer = Ridge(alpha=1.0)
        explainer.fit(X, y)
        
        # Get coefficients - positive means removing obstacle increases cost (important)
        # Negative means removing obstacle decreases cost (harmful for path planning)
        importance = explainer.coef_
        
        # Replace any infinite values with large finite values to avoid rendering errors
        importance = np.nan_to_num(importance, nan=0.0, posinf=1000.0, neginf=-1000.0)
        
        # Restore the original environment completely
        self.env = original_env_state
        
        return importance
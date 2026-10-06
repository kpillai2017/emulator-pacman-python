import pygame
import pygame.gfxdraw
from dataclasses import dataclass

@dataclass
class Input:
    """
    Input handler class for managing keyboard and mouse input in pygame.
    Tracks key presses, releases, mouse clicks, and mouse movement.
    """
    # Mouse button constants for easy reference
    MOUSE_LEFT = 0
    MOUSE_MIDDLE = 1
    MOUSE_RIGHT = 2

    def __init__(self):
        """Initialize the input handler with empty state containers."""
        self.events = {}  # Dictionary to store pygame events
        self.keys = {}  # dict: keycode -> bool (current key states)
        self.prev_keys = {}  # Previous frame's key states for edge detection
        self.key_hits = set()  # Keys that were just pressed this frame
        self.key_ups = set()  # Keys that were just released this frame

        # Mouse state tracking
        self.mouse_keys = [False for i in range(3)]  # Current state of 3 mouse buttons
        self.prev_mouse_keys = [False for i in range(3)]  # Previous frame's mouse button states
        self.mouse_hits = set()  # Mouse buttons that were just pressed
        self.mouse_ups = set()  # Mouse buttons that were just released
        self.mouse_x = 0  # Current mouse X coordinate
        self.mouse_y = 0  # Current mouse Y coordinate

    def init(self) -> None:
        """Initialize/reset the input handler state. Call this at the start of the game loop."""
        self.events = {}
        self.keys = {}
        self.prev_keys = {}
        self.key_hits = set()
        self.key_ups = set()
        self.mouse_hits = set()
        self.mouse_ups = set()
        # Get initial mouse position from pygame
        self.mouse_x, self.mouse_y = pygame.mouse.get_pos()
        self.mouse_keys = [False for i in range(3)]
        self.prev_mouse_keys = [False for i in range(3)]
        self.quit_event = False  # Flag to track if quit event was triggered

    def kill(self) -> None:
        """Clean up and reset all input state. Call this when shutting down."""
        self.events = {}
        self.keys = {}
        self.prev_keys = {}
        self.key_hits = set()
        self.key_ups = set()
        self.mouse_hits = set()
        self.mouse_ups = set()
        self.events = {}  # Clear events container (must stay a dict for get_event)

    def process_event(self, event):
        """
        Process a single pygame event and update internal state accordingly.
        
        Args:
            event: pygame event object to process
        """
        if event.type == pygame.QUIT:
            # User clicked the window close button
            self.events[pygame.QUIT] = True
        elif event.type == pygame.KEYDOWN:
            # Key was just pressed down
            self.keys[event.key] = True
            self.key_hits.add(event.key)
        elif event.type == pygame.KEYUP:
            # Key was just released
            self.keys[event.key] = False
            self.key_ups.add(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            # Mouse button was just pressed
            if event.button <= 3:  # Only handle left, middle, right buttons
                self.mouse_keys[event.button - 1] = True
                self.mouse_hits.add(event.button - 1)
        elif event.type == pygame.MOUSEBUTTONUP:
            # Mouse button was just released
            if event.button <= 3:  # Only handle left, middle, right buttons
                self.mouse_keys[event.button - 1] = False
                self.mouse_ups.add(event.button - 1)
        elif event.type == pygame.MOUSEMOTION:
            # Mouse was moved, update position
            self.mouse_x, self.mouse_y = event.pos

    def update(self) -> None:
        """
        Update input state for the current frame. Call this once per game loop iteration.
        Clears edge-triggered events and processes all pending pygame events.
        """
        # Clear frame-specific events (hits and releases) from last frame
        self.key_hits.clear()
        self.key_ups.clear()
        self.mouse_hits.clear()
        self.mouse_ups.clear()
        
        # Store previous frame's state for edge detection
        self.prev_keys = self.keys.copy()
        self.prev_mouse_keys = self.mouse_keys[:]
        
        # Update mouse position and button states from pygame
        self.mouse_x, self.mouse_y = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        for i in range(min(3, len(mouse_pressed))):
            self.mouse_keys[i] = mouse_pressed[i]
    
        # Process all pending pygame events
        for event in pygame.event.get():
            self.process_event(event)

    def get_event(self, key: int) -> bool:
        """Check if a specific pygame event occurred this frame."""
        return self.events.get(key, False)

    def key_down(self, key: int) -> bool:
        """Check if a key is currently being held down."""
        return self.keys.get(key, False)

    def key_hit(self, key: int) -> bool:
        """Check if a key was just pressed this frame (edge-triggered)."""
        return key in self.key_hits

    def key_up(self, key: int) -> bool:
        """Check if a key was just released this frame (edge-triggered)."""
        return key in self.key_ups

    def mouse_down(self, key: int) -> bool:
        """Check if a mouse button is currently being held down."""
        if key < 0 or key > 2:
            return False
        return self.mouse_keys[key]

    def mouse_hit(self, key: int) -> bool:
        """Check if a mouse button was just pressed this frame (edge-triggered)."""
        return key in self.mouse_hits

    def mouse_up(self, key: int) -> bool:
        """Check if a mouse button was just released this frame (edge-triggered)."""
        return key in self.mouse_ups

    def get_mouse_x(self) -> int:
        """Get the current mouse X coordinate."""
        return self.mouse_x

    def get_mouse_y(self) -> int:
        """Get the current mouse Y coordinate."""
        return self.mouse_y

    def set_mouse_pos(self, x: int, y: int) -> None:
        """Set the mouse cursor position to the specified coordinates."""
        pygame.mouse.set_pos([x, y])

    def hide_cursor(self, hide: bool) -> None:
        """Show or hide the mouse cursor."""
        if hide:
            pygame.mouse.set_visible(False)
        else:
            pygame.mouse.set_visible(True)


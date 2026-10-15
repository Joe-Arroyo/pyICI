"""GUI sections for the pyICI customtkinter interface.

Each module is one section of the app (data loading, pulse verification,
regression, kinetic analysis) plus the shared column-mapping dialog. Sections
are thin presentation that call the pure ``analysis`` layer; `main_gui` composes
them into the app shell.
"""

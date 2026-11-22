# Design

Two tokens split the roles: `--field-border` for the resting outline, `--control-border` (unchanged, 3:1 on surface and surface-2) for hover, focus and selected states. Keyboard users still get the 2px focus ring (3:1) and a darker border on focus; pointer users get the darker border on hover. A resting field remains distinguishable by its outline and its 44px size, but its outline alone no longer meets 3:1: this is the accepted trade, recorded here and in the spec. Status dots and risk pills are not controls and are unchanged.

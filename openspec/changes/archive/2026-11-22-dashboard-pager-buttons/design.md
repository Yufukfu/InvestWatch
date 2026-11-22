# Design

A disabled button is exempt from contrast rules, and the `disabled` attribute already tells assistive technology and blocks the click. The pager is the one place where the two buttons sit side by side, so a faded one reads as a different colour rather than as unavailable. The pager keeps full opacity on a disabled button and shows the state with the `not-allowed` cursor and by having no hover effect (the hover rule already excludes `:disabled`). Other disabled buttons keep the shared 55% opacity.

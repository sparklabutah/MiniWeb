# Guide: configure_by_form

Configure one or more options on a settings or generator page and apply the changes.

## Preconditions

- The browser is on the page containing the settings form, generator, or configuration panel.

## Steps

1. Locate the form control (dropdown, slider, checkbox, radio button, text field, or toggle switch) corresponding to the setting to be changed.
2. Interact with the control to set it to the desired value (e.g., select an option, drag a slider, toggle a switch, or type a value).
3. Repeat the adjustment process for any other settings that need to be configured on the same page.
4. Locate and click the submission button (such as 'Save', 'Update', 'Regenerate', or 'Apply') to commit the changes, unless the interface explicitly autosaves on change.

## Watch for

- The control visually reflecting the new state (e.g., the correct option displayed in the dropdown, the slider showing the target number, or the toggle switched on/off).
- A success message, toast notification, or page reload confirming that the changes have been successfully saved.

## Pitfalls

- Navigating away from the page without clicking the 'Save' or 'Submit' button, causing the changes to be lost.
- Failing to scroll down to locate the save button if it is positioned at the bottom of a long form.
- Accidentally selecting an adjacent option in a dense dropdown list or misaligning a slider value.

## Variants

- **the setting is controlled by a dropdown menu** — Click the dropdown to open the options, select the target option, and click to confirm the selection.
- **the setting is controlled by a slider or range input** — Drag the slider handle or click along the track until the indicator displays the target numerical value.
- **the setting is controlled by a checkbox, radio button, or toggle switch** — Click directly on the element or its associated label to toggle its state to the desired option.

## Done when

The form is submitted, the page updates, or a confirmation message appears indicating the settings have been applied.

_Distilled by gemini-3.5-flash on 2026-09-27 from 12 human demonstrations on train sites only._

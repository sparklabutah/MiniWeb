# Guide: upload_file

Upload a file from the local system to a web application via the file picker dialog.

## Preconditions

- A file upload button, drag-and-drop zone, or attachment icon is visible on the page.

## Steps

1. Click the file upload button, drop zone, or attachment icon to trigger the system file picker.
2. In the file picker dialog, navigate to the folder containing the target file.
3. Select the target file.
4. Click the 'Open' or 'Choose' button in the dialog to confirm and attach the file.

## Watch for

- The file name, size, or a thumbnail preview appearing on the page near the upload area.
- A progress bar indicating the upload status.

## Pitfalls

- Selecting a file that exceeds the maximum size limit or is of an unsupported file type, which may cause the upload to fail silently or show an error.
- Clicking 'Cancel' instead of 'Open' in the system dialog, leaving the input empty.

## Variants

- **using automated browser tools that support direct file path input** — Target the hidden or visible file input element directly and set its value to the absolute path of the file.
- **the interface supports drag-and-drop** — Drag the file from your local file explorer and drop it directly onto the designated upload area.

## Done when

The file is successfully listed as an attachment, or its preview/thumbnail is displayed on the page.

_Distilled by gemini-3.5-flash on 2026-09-27 from 22 human demonstrations on train sites only._

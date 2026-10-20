## Calendar (com.apple.iCal) · appkit
Anchors: window#CALMainWindow main window root (role flips window/dialog) · button#MiniCalPrevMonthButton mini calendar previous month · button#MiniCalNextMonthButton mini calendar next month · unknown#sidebar-mini-month sidebar mini month grid · group#active-view main calendar view area · statictext#title-field event inspector title · statictext#notes-field event inspector notes · combobox#calendar-button event calendar picker · button#date-time-button event date and time · button#"previous day" previous period button · button#today-button today button · button#"next day" next period button
Quirk non_unique_role_name: use native_id first, else pre-order index checked by bounds
Quirk user_data_in_id: store only the prefix; match the row by index or value at run time
Quirk mass_focused: real focus is the focused list/outline container, not its cells
Quirk zero_area_clones: exclude zero-area nodes from resolution
Quirk window_id_drift: re-pick window each session; never cache window id

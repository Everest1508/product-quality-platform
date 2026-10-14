# Projects: phases, Pod and the log

Every product is also a project with a life: **Creation, FE, BE, Connection, Deploy, Testing, UAT, Live, Close.**
Open **Projects** in the sidebar.

## Board and Journey

- **Board:** a column for each phase. Drag a card to move it. Owners and admins see "+ Add project" in each column.
- **Journey:** one row per project, nine steps, with the date each step was reached. Click a step to move there.
- A phase the project does not use is grayed out while you drag ("Not part of this project"), and moving skips it.

## Moving a project

Who can move: the project lead, the **Pod** (the people assigned), owners and admins. You always have to say **why**.
The reason becomes a log entry with your name and the time, and the Pod is told. Moving back is allowed and is marked "sent back".

## The log

Open a project, then **Lifecycle**. Everyone on the Pod can add an update, blocker or decision, and tag another Pod member with `@name`.
Tagged people get a "mentioned you" notification; the rest of the Pod hears about the entry too. Entries cannot be edited or deleted;
add a **Correction** entry if you got something wrong.

## Plan and details

**New project** (or **Plan & details** on an existing one) holds: start and end dates, lead and Pod, tech stack, SRS text,
the phases the project uses, a schedule for each phase (dates and/or hours, inside the project dates), and **Crunch** items.

## Crunch

A Crunch item is a feature that has to ship before the project's end date: the feature, a due date, a reason, and a done tick.
Cards show the next Crunch date; it turns orange three days before and red when late.

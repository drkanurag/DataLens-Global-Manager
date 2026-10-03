# DataLens People Dashboard — Location-Based Access

## Run it

Use Python 3.11+ and install the three backend requirements:

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Then open [http://localhost:8000/dashboard/](http://localhost:8000/dashboard/).

## Demo employee IDs

Use `EMP001` for New Delhi, `EMP002` for Mumbai, or `EMP003` for Bengaluru. The complete dummy employee access directory is at `data/access_directory.csv`.

The server creates a session only after a valid employee ID is entered. Every dashboard and chatbot request carries that session token. The API then applies a server-side location filter before it applies any requested dashboard filter. A user cannot retrieve another city's data by changing a browser filter or calling an API endpoint.

> This is a demo authentication mechanism only. Do not use employee ID alone in production. Use your company SSO, HTTPS, secure token storage, expiry/refresh, audit logging, and a governed user-to-location access table.

## Power BI integration

Use the same governed `employee_id → location` mapping as a security table in the Power BI semantic model. Create a relationship from `Access[location]` to the employee-data location, then create a role with this DAX filter on the access table:

```DAX
Access[UPN] = USERPRINCIPALNAME()
```

Assign users/groups to the role in the Power BI Service and test with **View as**. This applies native Power BI Row-Level Security (RLS), including when users use filters, export data, or interact with visuals. The web chatbot can be hosted separately and supplied the Power BI identity/filter context through a custom visual or embedded-report application; never rely only on hiding a slicer.

## Tableau integration

Create a user-location entitlement table with `username` and `location`, join/relate it to the employee data by location, and add a data-source filter:

```tableau
[Username] = USERNAME()
```

Publish the data source and workbook, then validate with **Preview as User**. For an embedded Tableau dashboard, pass the authenticated user's identity to Tableau using Trusted Authentication or Connected Apps/JWT. The chatbot should read the same server-side entitlement after the host application validates that identity.

## Embedding in Power BI or Tableau

The dashboard is platform-neutral: it is a web application powered by the same filter state and governed data API. Embed it in a Power BI HTML/custom visual or Tableau dashboard extension/web object, then pass report filter changes to `/api/chat` and the existing analytics endpoints. The included UI is immediately functional with the workbook and exposes a deterministic, data-grounded assistant; it does not claim to be an in-product native chatbot until the relevant Power BI/Tableau extension is configured.


## Demo access roles

The access directory includes one global demo manager: `MANAGER001`. Its role is `Manager` and its location is `All Locations`. Manager sessions can view all locations and may use the dashboard Location scope filter. Employee sessions remain restricted to their authorised location.

Data-quality counts returned by `/api/analytics/data-quality` and `/api/chat` use the same secured data scope, so an employee sees only error counts for their authorised location while the global manager can see all locations or a selected location.

## UI upgrade

The frontend has been upgraded with an enterprise-style responsive layout, interactive SVG charts, click-to-filter behavior for location/department/job family/month, a data-quality center, searchable employee records, improved AI context display, global-manager scope indicators, and dark mode. The server-side authorization remains the source of truth for every analytics and chatbot request.

## Demo manager

`MANAGER001` is the global demo manager. Employees remain restricted to their authorized location. Data-quality counts in the dashboard and chatbot are always calculated from the current server-authorized scope.


## Latest UI and data-quality update

The dashboard now includes seven configured data-quality error types. The four newly added demo error types are Department Code is not matching EC vs SAP (12), Incorrect Business Email (10), Manager is not matching EC vs SAP (9), and Company Code is not matching EC vs SAP (7). These counts are dummy demo values and are scoped by authorized location in the API and chatbot.

Demo global manager: MANAGER001 (Alex Morgan). Employee IDs remain location-restricted.

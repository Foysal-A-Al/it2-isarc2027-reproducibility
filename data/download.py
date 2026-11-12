"""Download the seven public IFC models used in the study into data/ifc/.

Sources (accessed 28 September 2026):
  buildingSMART Sample-Test-Files (Simple-Scene, IFC4.3 ADD2)
  buildingSMART Community-Sample-Test-Files (Duplex Apartment, Medical-Dental Clinic; Git LFS)
Please respect the licences stated in those repositories.
"""
import pathlib, urllib.parse, urllib.request

OUT = pathlib.Path(__file__).parent / "ifc"
SAMPLE = "https://raw.githubusercontent.com/buildingSMART/Sample-Test-Files/main/"
COMMUNITY = "https://media.githubusercontent.com/media/buildingsmart-community/Community-Sample-Test-Files/main/"
FILES = {
    "Simple-Scene_Building-Hvac_IFC4X3.ifc": SAMPLE + "IFC 4.3.2.0 (IFC 4.3 ADD2)/Simple-Scene/Building-Hvac.ifc",
    "Simple-Scene_Infra-Plumbing_IFC4X3.ifc": SAMPLE + "IFC 4.3.2.0 (IFC 4.3 ADD2)/Simple-Scene/Infra-Plumbing.ifc",
    "Duplex_MEP_20110907.ifc": COMMUNITY + "IFC 2.3.0.1 (IFC 2x3)/Duplex Apartment/Duplex_MEP_20110907.ifc",
    "Duplex_Electrical_20121207.ifc": COMMUNITY + "IFC 2.3.0.1 (IFC 2x3)/Duplex Apartment/Duplex_Electrical_20121207.ifc",
    "Duplex_Plumbing_20121113.ifc": COMMUNITY + "IFC 2.3.0.1 (IFC 2x3)/Duplex Apartment/Duplex_Plumbing_20121113.ifc",
    "Clinic_HVAC.ifc": COMMUNITY + "IFC 2.3.0.1 (IFC 2x3)/Medical-Dental Clinic/Clinic_HVAC.ifc",
    "Clinic_Plumbing.ifc": COMMUNITY + "IFC 2.3.0.1 (IFC 2x3)/Medical-Dental Clinic/Clinic_Plumbing.ifc",
}

# Optional display context is outside the seven research inputs.
CONTEXT_FILES = {
    'context/Duplex_A_20110907.ifc': COMMUNITY + 'IFC 2.3.0.1 (IFC 2x3)/Duplex Apartment/Duplex_A_20110907.ifc',
}

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, url in {**FILES, **CONTEXT_FILES}.items():
        dest = OUT / name
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.stat().st_size > 10_000:
            print("exists  ", name); continue
        # Encode spaces in repository paths; the host/root URL remains unchanged.
        base, path = url.split("/main/", 1)
        full = base + "/main/" + urllib.parse.quote(path)
        print("fetching", name)
        urllib.request.urlretrieve(full, dest)
        head = dest.read_bytes()[:200]
        # Reject Git LFS pointers or HTML responses before treating the download as an IFC.
        if not head.startswith(b"ISO-10303-21"):
            raise RuntimeError(f"{name}: not an IFC file (Git LFS pointer?). Check the URL.")
    print("done:", OUT)

if __name__ == "__main__":
    main()

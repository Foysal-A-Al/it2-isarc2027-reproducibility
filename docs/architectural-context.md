# Federated building viewer

The overview can display an architectural IFC alongside the audited MEP model. Context never changes source hashes, audit metrics, revision matching, or finding IDs. Both sources retain their original world coordinates in metres. STEP IDs are local to each IFC: architectural IDs cannot select or highlight MEP findings.

Use **Open full building example**, then **Show 3D for this IFC**. Alternatively choose an architectural source under View controls and upload an IFC. Camera options include perspective, plan, and front, with adjustable context transparency. The initial 3D view remains off; model changes reset it. Context selection is scoped to the audited model hash and cached by the context content hash.

Bounds overlap is a coordinate sanity check, not proof of detailed alignment. Disjoint models produce a measured-gap warning. No inferred translation, rotation, made-up walls, or substituted network is applied.

## Public example and attribution

BSI (2020), **Duplex Apartment Test Files**, buildingSMART International. Source: https://github.com/buildingsmart-community/Community-Sample-Test-Files/tree/main/IFC%202.3.0.1%20(IFC%202x3)/Duplex%20Apartment

Architectural file: `Duplex_A_20110907.ifc`, downloaded unchanged under **CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/). Original authors retain attribution. `data/download.py` saves this optional display context beneath `data/ifc/context/`, separate from the seven study inputs. The bundled MEP and architecture are discipline exports from this public Duplex dataset; review their coordinates before treating visual proximity as an engineering relationship.

The generated concept was illustrative. The real viewer shows only geometry contained in the selected sources, including their actual proportions and completeness. Extraction limits and unavailable geometry remain visible.

## Runtime recovery

The geometry worker writes atomic checkpoints after each 64 processed elements. If the time limit is reached, the caller can display completed real meshes with an explicit warning and count unprocessed elements as omitted. A timeout without a usable checkpoint remains an explicit unavailable-geometry warning. No partial coverage is described as full coverage.

from blendbridge.client import BlendBridge
from matching_library import run_full_pipeline
import json

SPRING_LEN = 100.0
TAB_LEN    = 10.0
SPRING_THICK = 1.2

with BlendBridge() as c:
    c.call("clear_scene", keep_camera=False)
    c.call("blendgen_flat_spring",
            spring_length=SPRING_LEN, spine_type="SINUSOID",
            end_tab_length=TAB_LEN)

    stl_path = "/tmp/spring.stl"
    bc_path = "/tmp/bc_groups.json"
    c.call("export_stl", filepath=stl_path)
    

    mesh_stats = c.call("get_mesh_stats", object_name="FlatSpring")

    fixed = c.call("select_faces_by_bbox",
                    object_name="FlatSpring",
                    bbox_max=[None, -TAB_LEN, None])
    slide = c.call("select_faces_by_bbox",
                    object_name="FlatSpring",
                    bbox_max=[None,  None, -SPRING_THICK/2.0])
    force = c.call("select_faces_by_bbox",
                    object_name="FlatSpring",
                    bbox_min=[None,  SPRING_LEN+TAB_LEN, 0.0])

bc = {
    "schema_version": 1, "source": "blendbridge", "mode": "mesh",
    "step_file": stl_path, "units": "millimeters",
    "groups": {"fixed": fixed, "slide": slide, "force": force},
    "mesh_stats": mesh_stats,
}
with open(bc_path, "w") as f:
    json.dump(bc, f)

report = run_full_pipeline(bc_path, stl_path, "/tmp/output.msh")
print(report.group_stats)

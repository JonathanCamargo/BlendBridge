from blendbridge.client import BlendBridge
with BlendBridge() as client:
    # Generate a gripper finger with ridges
    result = client.call("blendgen_gripper_finger",
                        finger_length=100,
                        base_width=25,
                        texture_type="RIDGES",
                        ridge_count=8)
    print(f"Created: {result['name']} with {result['vertices']} vertices")
    
    # Generate a flat spring
    result = client.call("blendgen_flat_spring",
                        spring_length=80,
                        spine_type="SINUSOID")
    
    # Export to STL
    result = client.call("blendgen_flat_spring_export",
                        output_path="/tmp/spring.stl",
                        spring_length=100)
bl_info = {
    "name": "Trackmania Spectators Helper",
    "description": "This plugin quickly exports the positions and rotations of 'Hair Particle system' instances, in order to be used in Trackmania to define spectator positions on custom items edited with E++.",
    "author": "florenzius (and ChatGPT lol)",
    "version": (2, 0),
    "blender": (4, 3, 0),
    "warning": "Create particle system on your object (select 'Hair'!), then select it in Object mode. You will find the export options in the N-Menu's 'Tools' tab.",
    "category": "Object",
}

import bpy
import math
import os
import mathutils

# Relative Path --> Absolute Path
def make_absolute(path):
    blend_file_path = bpy.data.filepath
    directory = os.path.dirname(blend_file_path)
    return os.path.abspath(os.path.join(directory, path))

# Logic for Euler rotation to quaternions
def euler_to_quaternion(rot_x, rot_y, rot_z):
    # Convert to radians
    rot_x_rad = math.radians(rot_x)
    rot_y_rad = math.radians(rot_y)
    rot_z_rad = math.radians(rot_z)

    # Create euler object
    euler_rotation = mathutils.Euler((rot_x_rad, rot_z_rad, rot_y_rad), 'XZY')

    # Convert euler object to quaternion
    quaternion_rotation = euler_rotation.to_quaternion()
    
    return quaternion_rotation

# Round quaternion values
def round_quaternion(quaternion):
    rounded_quaternion = (
        round(quaternion.w, 1),
        round(quaternion.x, 1),
        round(quaternion.y, 1),
        round(quaternion.z, 1)
    )
    return rounded_quaternion

# Remove duplicate positions
def remove_duplicate_positions(data):
    unique_data = []
    seen_positions = set()
    for entry in data:
        position = entry[4:7]  # Extract pos info (X, Z, Y)
        position_tuple = tuple(position)
        if position_tuple not in seen_positions:
            seen_positions.add(position_tuple)
            unique_data.append(entry)
    return unique_data

# Open file browser and save selected path
class OBJECT_OT_set_export_path(bpy.types.Operator):
    bl_idname = "object.set_export_path"
    bl_label = "Set Export Path"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.export_path = bpy.path.abspath("//")
        return {'FINISHED'}

# Export particle positions data
class OBJECT_OT_export_particle_positions(bpy.types.Operator):
    bl_idname = "object.export_particle_positions"
    bl_label = "Export positions"
    bl_options = {'REGISTER', 'UNDO'}

    # File ImportHelper
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={'HIDDEN'})

    def execute(self, context):
        print("Starting positions export...")

        # Check whether object is selected
        if context.object is None:
            self.report({'ERROR'}, "No object selected.")
            return {'CANCELLED'}

        # Check for existing particle/hair system
        if context.object.type != 'MESH' or context.object.particle_systems.active is None:
            self.report({'ERROR'}, "Selected object does not have a hair particle system.")
            return {'CANCELLED'}

        # Get active particle system
        particle_system = context.object.particle_systems.active

        # Get hair particle data
        depsgraph = context.evaluated_depsgraph_get()
        object_eval = context.object.evaluated_get(depsgraph)
        particles = object_eval.particle_systems.active.particles

        # Get object and its pivot point
        obj = context.object
        pivot_point = obj.location

        # Convert export path to absolute path
        file_name = context.scene.export_name or "PosExport"
        file_path = make_absolute(os.path.join(bpy.context.scene.export_path, f"{file_name}.csv"))

        print(f"Writing to file: {file_path}")

        # Check, ob appended werden soll
        mode = 'a' if context.scene.append_to_file else 'w'

        # Open file writer
        with open(file_path, mode) as file:
            # Check whether table head is wanted
            if context.scene.add_column_names and mode == 'w':
                # Create table head
                file.write("quatW,quatX,quatY,quatZ,posX,posZ,posY\n")

            if mode == 'a':
                file.write("\n")

            # Sort by z-axis values ascending
            particles_sorted = sorted(particles, key=lambda particle: particle.location.z)

            # Write quaternion and position data relative to pivot
            particle_data = []
            for i, particle in enumerate(particles_sorted):
                rotation = particle.rotation
                position = particle.location - pivot_point
                rounded_position = (
                    round(position.x, 2),
                    round(position.z - 1, 2),  # Swap Y and Z as TM is Y-Up. -1 because for some reason z values would be offset by 1m
                    round(position.y, 2)
                )

                # Conversion of euler to quaternion
                quaternion_rotation = euler_to_quaternion(context.scene.rotation_x, context.scene.rotation_y, context.scene.rotation_z)

                # Apply custom rotation values
                adjusted_rotation = rotation @ quaternion_rotation

                # Check for mirroring
                if context.scene.mirror_x:
                    rounded_position = (-rounded_position[0], rounded_position[1], rounded_position[2])
                if context.scene.mirror_y:
                    rounded_position = (rounded_position[0], rounded_position[1], -rounded_position[2])
                if context.scene.mirror_z:
                    rounded_position = (rounded_position[0], -rounded_position[1], rounded_position[2])

                # Round quaternion values
                rounded_rotation = round_quaternion(adjusted_rotation)

                particle_data.append(
                    (rounded_rotation[0], rounded_rotation[1], rounded_rotation[2], rounded_rotation[3],
                     rounded_position[0], rounded_position[1], rounded_position[2])
                )

                # print(f"Particle {i}: Quaternion {rounded_rotation}, "
                #      f"Position {rounded_position[0]}, {rounded_position[1]}, {rounded_position[2]}")

            # Remove double positions
            original_count = len(particle_data)
            particle_data = remove_duplicate_positions(particle_data)
            removed_count = original_count - len(particle_data)

            print(f"Removed {removed_count} duplicate positions.")

            # Write data to file
            for entry in particle_data:
                file.write(f"{entry[0]},{entry[1]},{entry[2]},{entry[3]},{entry[4]},{entry[5]},{entry[6]}\n")

            # Remove empty lines in entire file after writing data
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    lines = file.readlines()
                lines = [line for line in lines if line.strip() != '']
                with open(file_path, 'w') as file:
                    file.writelines(lines)

        self.report({'INFO'}, f"Spectator positions exported to {file_path}.")
        print("Export successful.")

        # Open folder and/or file based on user preferences
        if context.scene.open_folder:
            bpy.ops.wm.path_open(filepath=os.path.dirname(file_path))
        if context.scene.open_file:
            bpy.ops.wm.path_open(filepath=file_path)   

        return {'FINISHED'}

# GUI-Panel and elements
class OBJECT_PT_particle_position_exporter_panel(bpy.types.Panel):
    bl_label = "Trackmania Spectators Helper"
    bl_idname = "PT_particle_position_exporter_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # File browser for path and file name
        layout.prop(context.scene, "export_path", text="Output Path")
        layout.prop(context.scene, "export_name", text="File Name")
        layout.operator(OBJECT_OT_set_export_path.bl_idname, text="Set path to current folder")

        # Checkboxes extra
        layout.prop(context.scene, "add_column_names", text="Add column names")
        layout.prop(context.scene, "append_to_file", text="Append to existing file")
        layout.prop(context.scene, "open_folder", text="Open folder after export")
        layout.prop(context.scene, "open_file", text="Open file after export")

        layout.separator()

        # Rotation (X, Y, Z) Input
        layout.prop(context.scene, "rotation_x")
        layout.prop(context.scene, "rotation_y")
        layout.prop(context.scene, "rotation_z")

        # Mirror (X, Y, Z) Checkboxes
        layout.prop(context.scene, "mirror_x", text="Mirror X")
        layout.prop(context.scene, "mirror_y", text="Mirror Y")
        layout.prop(context.scene, "mirror_z", text="Mirror Z")

        layout.separator()

        # Disclaimer
        layout.label(text="Output format: '(Quaternion: w, x, y, z), x, y, z'")

        # Export-Button
        layout.operator(OBJECT_OT_export_particle_positions.bl_idname, text="Export positions")

# Function for export menu
def menu_func_export(self, context):
    self.layout.operator(OBJECT_OT_export_particle_positions.bl_idname, text="Spectator positions")

# Blender shenanigans
def register():
    bpy.utils.register_class(OBJECT_OT_export_particle_positions)
    bpy.utils.register_class(OBJECT_OT_set_export_path)
    bpy.utils.register_class(OBJECT_PT_particle_position_exporter_panel)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    # Neue Properties für die UI-Komponenten
    bpy.types.Scene.export_path = bpy.props.StringProperty(subtype='DIR_PATH')
    bpy.types.Scene.export_name = bpy.props.StringProperty(subtype='FILE_NAME', default="PosExport")

    bpy.types.Scene.rotation_x = bpy.props.FloatProperty(name="Rotation X")
    bpy.types.Scene.rotation_y = bpy.props.FloatProperty(name="Rotation Y")
    bpy.types.Scene.rotation_z = bpy.props.FloatProperty(name="Rotation Z")

    bpy.types.Scene.mirror_x = bpy.props.BoolProperty(name="Mirror X")
    bpy.types.Scene.mirror_y = bpy.props.BoolProperty(name="Mirror Y")
    bpy.types.Scene.mirror_z = bpy.props.BoolProperty(name="Mirror Z")

    # Neue Property für den Tabellenkopf
    bpy.types.Scene.add_column_names = bpy.props.BoolProperty(name="Add column names")
    bpy.types.Scene.open_folder = bpy.props.BoolProperty(name="Open folder after export")
    bpy.types.Scene.open_file = bpy.props.BoolProperty(name="Open file after export")

    bpy.types.Scene.append_to_file = bpy.props.BoolProperty(
    name="Append to existing file", default=False)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_export_particle_positions)
    bpy.utils.unregister_class(OBJECT_OT_set_export_path)
    bpy.utils.unregister_class(OBJECT_PT_particle_position_exporter_panel)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    # Entferne die hinzugefügten Properties
    del bpy.types.Scene.export_path
    del bpy.types.Scene.rotation_x
    del bpy.types.Scene.rotation_y
    del bpy.types.Scene.rotation_z

    del bpy.types.Scene.mirror_x
    del bpy.types.Scene.mirror_y
    del bpy.types.Scene.mirror_z

    del bpy.types.Scene.add_column_names
    del bpy.types.Scene.open_folder
    del bpy.types.Scene.open_file

    del bpy.types.Scene.append_to_file

if __name__ == "__main__":
    register()

import os
import numpy as np
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image
import io
import uuid

# Eliminated dependency on shape_generator and open3d
# We use our own write_colored_ply function defined below


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def generate_point_cloud_from_image(image_path, output_path, resolution_scale=0.5, z_scale=50.0):
    """
    Convert an image to a 3D point cloud based on pixel intensity.
    
    Args:
        image_path: Path to the input image
        output_path: Path to save the PLY file
        resolution_scale: Downscale factor to reduce point count (0.0 - 1.0)
        z_scale: Multiplier for the Z-axis (depth)
    """
    # Load image
    img = Image.open(image_path)
    
    # Convert to RGB for colors
    img_rgb = img.convert('RGB')
    
    # Resize for performance / point cloud density control
    new_width = int(img.width * resolution_scale)
    new_height = int(img.height * resolution_scale)
    img_rgb = img_rgb.resize((new_width, new_height))
    img_gray = img_rgb.convert('L') # Grayscale for depth
    
    # Convert to numpy arrays
    colors = np.array(img_rgb)
    depth_map = np.array(img_gray)
    
    # Create coordinate grid
    height, width = depth_map.shape
    x = np.linspace(0, width, width)
    y = np.linspace(0, height, height)
    xx, yy = np.meshgrid(x, y)
    
    # Flatten arrays
    flat_x = xx.flatten()
    flat_y = yy.flatten()
    flat_z = depth_map.flatten() / 255.0 * z_scale # Normalize 0-1 then scale
    
    # Invert Z if needed (usually lighter = closer, so higher Z)
    # But for a "depth map" sometimes darker is deeper. 
    # Let's assume lighter is "higher" (hills) for now.
    
    points = np.column_stack((flat_x, flat_y, flat_z))
    
    # Labels: 
    # The existing write_ply_with_labels requires a label per point.
    # We'll just define a new label "5" for "Image Generated" or reuse 1 (Horizontal)
    # Let's use 0 (Undefined) or 1. Let's use 1 to show up as "Tan" or customize later.
    # Actually, to keep it simple and avoid modifying the reader, we'll just use 1.
    labels = np.ones(points.shape[0], dtype=int)
    
    # Note: write_ply_with_labels defines colors based on labels in its viewer, 
    # but the PLY file itself just stores x,y,z,label.
    # To get REAL colors in a PLY properly, we usually add r,g,b properties.
    # The current 'write_ply_with_labels' implementation DOES NOT support custom RGB colors.
    # It only supports labels.
    # WE WILL MODIFY THE WRITE FUNCTION locally here to support RGB if we want colors,
    # OR we just stick to geometry.
    # For a premium feel, colors are important. 
    # Let's create a custom writer here to include RGB.
    
    write_colored_ply(points, colors.reshape(-1, 3), output_path)

def write_colored_ply(points, colors, filename):
    """
    Write a PLY file with X, Y, Z and R, G, B colors.
    """
    header = """ply
format ascii 1.0
element vertex {}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
""".format(len(points))

    with open(filename, 'w') as f:
        f.write(header)
        for i in range(len(points)):
            p = points[i]
            c = colors[i]
            f.write(f"{p[0]} {p[1]} {p[2]} {int(c[0])} {int(c[1])} {int(c[2])}\n")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400
        
    # Generate unique filenames
    unique_id = str(uuid.uuid4())
    img_filename = f"{unique_id}_{file.filename}"
    img_path = os.path.join(app.config['UPLOAD_FOLDER'], img_filename)
    
    ply_filename = f"{unique_id}.ply"
    ply_path = os.path.join(app.config['OUTPUT_FOLDER'], ply_filename)
    
    file.save(img_path)
    
    try:
        # Tweakable parameters from form? For now hardcode or defaults
        scale = float(request.form.get('scale', 0.5))
        z_intensity = float(request.form.get('z_intensity', 50.0))
        
        generate_point_cloud_from_image(img_path, ply_path, resolution_scale=scale, z_scale=z_intensity)
        
        return jsonify({
            'success': True,
            'ply_url': f"/download/{ply_filename}"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename))

if __name__ == '__main__':
    app.run(debug=True, port=5000)

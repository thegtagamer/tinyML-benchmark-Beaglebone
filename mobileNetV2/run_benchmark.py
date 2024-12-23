import os
import time
import csv
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt
from PIL import Image
import tflite_runtime.interpreter as tflite
import psutil  # For monitoring CPU and memory usage

# Constants

MODEL_PATH = "./models/quantized_deeplabv3_mobilenet_v2.tflite"
DATASET_DIR = "./dataset"
VISUALIZATION_DIR = "./visualizations"
RESULTS_FILE = os.path.join(VISUALIZATION_DIR, "benchmark_results.csv")

# Create visualization directory
os.makedirs(VISUALIZATION_DIR, exist_ok=True)

# Load dataset
def load_dataset(dataset_dir):
    image_paths = [
        os.path.join(dataset_dir, f) for f in os.listdir(dataset_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ]
    if not image_paths:
        raise FileNotFoundError(f"No image files found in {dataset_dir}")
    return image_paths

# Preprocess image
def preprocess_image(image_path, input_shape):
    """
    Preprocess the input image to match the model's input requirements.
    Args:
        image_path (str): Path to the image file.
        input_shape (list): Expected input shape of the model (e.g., [1, 3, height, width]).
    Returns:
        np.ndarray: Preprocessed image ready for inference.
    """
    img = Image.open(image_path).convert("RGB")  # Ensure the image has 3 channels (RGB)
    img = img.resize((input_shape[3], input_shape[2]))  # Resize to match height and width
    img_array = np.array(img, dtype=np.float32) / 255.0  # Normalize pixel values to [0, 1]
    img_array = np.transpose(img_array, (2, 0, 1))  # Change shape to [3, height, width]
    img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension to make it [1, 3, height, width]
    return img_array



# Run Powertop to fetch power consumption data
# def get_power_consumption():
#     try:
#         # Runs `powertop` and fetches the "Power consumption" value
#         result = os.popen("sudo powertop --time=5 --csv=temp.csv && tail -n 1 temp.csv").read()
#         # os.remove("temp.csv")  # Clean up the temporary file
#         # Extract the power consumption from the CSV
#         power = float(result.split(',')[-2])
#         return power
#     except Exception:
#         return np.nan  # Return NaN if powertop fails

# Benchmark function
def run_benchmark(interpreter, dataset_paths):
    inference_times = []
    predictions = []
    cpu_usages = []
    memory_usages = []
    # power_consumptions = []
    confidence_scores = []  # <====


    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    input_shape = input_details[0]['shape']  # [1, 3, height, width]

    for image_path in tqdm(dataset_paths, desc="Benchmarking Inference"):
        # Preprocess the image
        input_data = preprocess_image(image_path, input_shape)
        input_data = input_data.astype(input_details[0]['dtype'])  # Match expected dtype
        
        # Set the input tensor
        interpreter.set_tensor(input_details[0]['index'], input_data)
        
        # Monitor system metrics before inference
        cpu_before = psutil.cpu_percent(interval=None)
        mem_before = psutil.virtual_memory().percent

        # Measure inference time
        start_time = time.perf_counter()
        interpreter.invoke()
        end_time = time.perf_counter()
        
        # Monitor system metrics after inference
        cpu_after = psutil.cpu_percent(interval=None)
        mem_after = psutil.virtual_memory().percent

        # Fetch results
        inference_time = end_time - start_time
        inference_times.append(inference_time)

        cpu_usages.append((cpu_before + cpu_after) / 2)  # Average CPU usage
        memory_usages.append(mem_after)  # Memory usage at the end of inference

        # # Measure power consumption
        # power_consumptions.append(get_power_consumption())
        # Get the output tensor
        output = interpreter.get_tensor(output_details[0]['index'])
        predictions.append(output)
        confidence_scores.append(np.max(output))  # <==== Extract confidence score

    # return inference_times, cpu_usages, memory_usages, power_consumptions
    return inference_times, predictions, confidence_scores, cpu_usages, memory_usages


# Visualization functions
# def save_visualizations(inference_times, cpu_usages, memory_usages, power_consumptions):
def save_visualizations(inference_times, predictions, confidence_scores, cpu_usages, memory_usages):
    # Plot Inference Time
    plt.figure()
    plt.hist(inference_times, bins=20, color='blue', alpha=0.7)
    plt.title("Inference Time Distribution")
    plt.xlabel("Time (s)")
    plt.ylabel("Frequency")
    plt.savefig(os.path.join(VISUALIZATION_DIR, "inference_time_distribution.png"))
    plt.close()

    # Plot CPU Usage
    plt.figure()
    plt.plot(cpu_usages, color='orange')
    plt.title("CPU Usage Over Time")
    plt.xlabel("Iteration")
    plt.ylabel("CPU Usage (%)")
    plt.savefig(os.path.join(VISUALIZATION_DIR, "cpu_usage_plot.png"))
    plt.close()

    # Plot Memory Usage
    plt.figure()
    plt.plot(memory_usages, color='green')
    plt.title("Memory Usage Over Time")
    plt.xlabel("Iteration")
    plt.ylabel("Memory Usage (%)")
    plt.savefig(os.path.join(VISUALIZATION_DIR, "memory_usage_plot.png"))
    plt.close()

    # Plot Power Consumption
    # plt.figure()
    # plt.plot(power_consumptions, color='red')
    # plt.title("Power Consumption Over Time")
    # plt.xlabel("Iteration")
    # plt.ylabel("Power Consumption (W)")
    # plt.savefig(os.path.join(VISUALIZATION_DIR, "power_consumption_plot.png"))
    # plt.close()
    
    # Confidence Scores Over Time <====
    plt.figure()
    plt.plot(confidence_scores, color='purple')
    plt.title("Confidence Scores Over Time (MobileNet)")
    plt.xlabel("Iteration")
    plt.ylabel("Confidence Score")
    plt.savefig(os.path.join(VISUALIZATION_DIR, "mobilenet_confidence_scores_plot.png"))
    plt.close()

    # Predicted Labels Over Time <====
    plt.figure()
    predicted_labels = [np.argmax(pred) for pred in predictions]
    plt.plot(predicted_labels, color='cyan')
    plt.title("Predicted Labels Over Time (MobileNet)")
    plt.xlabel("Iteration")
    plt.ylabel("Predicted Label")
    plt.savefig(os.path.join(VISUALIZATION_DIR, "mobilenet_predicted_labels_plot.png"))
    plt.close()

# Save metrics to CSV
def save_results_to_csv(inference_times, predictions, confidence_scores, cpu_usages, memory_usages):
    """
    Save inference results to a CSV file.
    """
    with open(RESULTS_FILE, "w", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Iteration", "Inference Time (s)", "Predicted Label", "Confidence Score", "CPU Usage (%)", "Memory Usage (%)"])  # <====
        for i in range(len(inference_times)):
            predicted_label = np.argmax(predictions[i])
            csvwriter.writerow([i + 1, inference_times[i], predicted_label, confidence_scores[i], cpu_usages[i], memory_usages[i]])  # <====
    print(f"Benchmark results saved to {RESULTS_FILE}")

# Main Execution
def main():
    # Load TFLite model
    interpreter = tflite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()

    # Load dataset
    dataset_paths = load_dataset(DATASET_DIR)

    print("Running Benchmark...")
    # inference_times, cpu_usages, memory_usages, power_consumptions = run_benchmark(interpreter, dataset_paths)
    inference_times, predictions, confidence_scores, cpu_usages, memory_usages = run_benchmark(interpreter, dataset_paths)


    print("Saving visualizations...")
    # save_visualizations(inference_times, cpu_usages, memory_usages, power_consumptions)
    save_visualizations(inference_times, predictions, confidence_scores, cpu_usages, memory_usages)


    print("Saving results to CSV...")
    # save_results_to_csv(inference_times, cpu_usages, memory_usages, power_consumptions)
    save_results_to_csv(inference_times, predictions, confidence_scores, cpu_usages, memory_usages)


    print("Benchmark complete!")

if __name__ == "__main__":
    main()

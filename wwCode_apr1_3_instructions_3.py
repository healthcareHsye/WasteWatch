from flask import Flask, render_template_string, request, redirect, url_for, session 
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D
import psutil

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Replace with a secure key in production

previous_results = []  # Global list to store previous chart results

# Navigation bar HTML (used on all pages) wrapped in a white box
nav_bar = """
<div class="menu-box" style="background-color: #fff; border-radius: 8px; padding: 5px 10px; margin: 10px auto; max-width: 250px;">
  <div class="menu-bar" style="text-align:center; font-size: 1.1em;">
    <a href="/" style="margin-right:10px; text-decoration:none; color:#007BFF; font-weight:bold;">Tool</a>
    <a href="/instructions" style="text-decoration:none; color:#007BFF; font-weight:bold;">Instructions</a>
  </div>
</div>
"""

# ---------------------------
# Global HTML Template for Main (Simulation) Page
# ---------------------------
main_template = """
<!DOCTYPE html>
<html>
<head>
  <title>Wastewatch</title>
  <style>
    * { box-sizing: border-box; }
    body { background-color: #e0f7fa; font-family: Arial, sans-serif; margin: 20px; }
    h1 { text-align: center; }
    .menu-box { margin-bottom: 20px; }
    .intro { max-width: 800px; margin: 0 auto 20px; text-align: center; font-size: 1.1em; padding: 10px; background-color: #fff; border-radius: 8px; }
    .form-container { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 20px; max-width: 1200px; margin: 20px auto; background-color: #fff; padding: 20px; border-radius: 8px; }
    .column { flex: 1; min-width: 250px; margin: 10px; }
    .column h3 { margin-top: 0; }
    label { font-weight: bold; display: block; margin-top: 10px; }
    select, input[type="number"] { width: 100%; margin-top: 5px; padding: 5px; }
    .sub-section { margin-top: 10px; padding: 10px; background: #f7f7f7; border-radius: 4px; }
    .submit-container, .clear-container { text-align: center; margin-top: 20px; }
    #loading { display: none; text-align: center; font-size: 1.2em; font-weight: bold; margin-top: 20px; color: #333; }
    #results { max-width: 1200px; margin: 20px auto; text-align: center; }
  </style>
</head>
<body>
  <h1>Wastewatch</h1>
  {{ nav_bar|safe }}
  <div class="intro">
    <p>
      This simulation-based tool evaluates different statistical methods for detecting important changes in wastewater data related to epidemics.
      Use the form below to simulate baseline epidemic data, induce changes if desired, and analyze the detection performance.
    </p>
  </div>
  
  <!-- Main Input Form -->
  <form class="input-form" method="post" onsubmit="showLoading()">
    <div class="form-container">
      <!-- Column 1: Baseline Data -->
      <div class="column">
        <h3>Type of Baseline Data</h3>
        <label for="behaviorSelect">Behavior Type:</label>
        <select name="behavior" id="behaviorSelect">
          <option value="" disabled selected>Select behavior</option>
          <option value="stable">Stable</option>
          <option value="trending">Trending</option>
          <option value="periodic">Periodic</option>
          <option value="randomwalk" disabled style="color: gray;">Random Walk</option>
        </select>
        <div id="stableInputs" style="display:none;" class="sub-section">
          <label>Distribution Type (for stable):</label>
          <select name="dist_type">
            <option value="" disabled selected>Select distribution</option>
            <option value="normal">Normal</option>
            <option value="lognormal">Lognormal</option>
          </select>
          <label>Mean:</label>
          <input type="number" step="any" name="mean">
          <label>Standard Deviation:</label>
          <input type="number" step="any" name="std">
        </div>
        <div id="trendingInputs" style="display:none;" class="sub-section">
          <label>Start Value:</label>
          <input type="number" step="any" name="start">
          <label>Slope:</label>
          <input type="number" step="any" name="slope">
          <label>Noise Level:</label>
          <input type="number" step="any" name="noise">
        </div>
        <div id="periodicInputs" style="display:none;" class="sub-section">
          <label>Mean:</label>
          <input type="number" step="any" name="p_mean">
          <label>Amplitude:</label>
          <input type="number" step="any" name="amplitude">
          <label>Period:</label>
          <input type="number" step="any" name="period">
          <label>Noise Level:</label>
          <input type="number" step="any" name="p_noise">
        </div>
        <div class="sub-section">
          <label>Number of Days for Baseline Data:</label>
          <input type="number" name="n_baseline">
        </div>
      </div>
      
      <!-- Column 2: Change Information -->
      <div class="column">
        <h3>Type of Change</h3>
        <label>Do you want to induce a change?</label>
        <select name="induce_change">
          <option value="" disabled selected>Select...</option>
          <option value="yes">Yes</option>
          <option value="no">No</option>
        </select>
        <div id="changeInputs" style="display:none;" class="sub-section">
          <label>Day to Start the Change:</label>
          <input type="number" name="change_day">
          <label for="changeTypeSelect">Type of Change:</label>
          <select name="change_type" id="changeTypeSelect">
            <option value="" disabled selected>Select change type</option>
            <option value="step">Step Change</option>
            <option value="trending">Trending Change</option>
          </select>
          <div id="stepChange" style="display:none;">
            <label>Factor to Multiply the Current Mean:</label>
            <input type="number" step="any" name="factor">
          </div>
          <div id="trendingChange" style="display:none;">
            <label>Slope to be used during the Trending Change:</label>
            <input type="number" step="any" name="change_slope">
            <label>Number of Days for the Trend Change to Last:</label>
            <input type="number" name="trend_duration">
          </div>
        </div>
      </div>
      
      <!-- Column 3: Surveillance Method -->
      <div class="column">
        <h3>Surveillance Method</h3>
        <label for="analysisSelect">Analysis Method:</label>
        <select name="analysis_method" id="analysisSelect">
          <option value="" disabled selected>Select method</option>
          <option value="shewhart">Shewhart</option>
          <option value="ewma">EWMA</option>
          <option value="mc-ewma">MC-EWMA</option>
          <option value="cusum" disabled style="color: gray;">CUSUM</option>
          <option value="scan" disabled style="color: gray;">SCAN</option>
        </select>
        <div id="lambdaInput" style="display:none;" class="sub-section">
          <label>Choose your lambda option:</label>
          <select name="lam_option">
            <option value="" disabled selected>Select option</option>
            <option value="manual">Manual</option>
            <option value="optimized">Optimized</option>
          </select>
          <div id="manualLambda" style="display:none;">
            <label>Enter your lambda value (0 &lt; lambda &lt; 1):</label>
            <input type="number" step="any" name="lambda_val">
          </div>
        </div>
        <div class="sub-section">
          <label>Number of Replications:</label>
          <input type="number" name="n_replications">
          <label>How many sigmas would you like to use?</label>
          <input type="number" step="any" name="sigma_multiplier">
        </div>
      </div>
    </div>
    
    <div class="submit-container">
      <input type="submit" value="Analyze">
    </div>
  </form>
  
  <!-- Loading Indicator -->
  <div id="loading">Loading...</div>
  
  {% if full_params_exists %}
  <!-- Reanalysis Form in a White Box -->
  <br>
  <div class="form-container" style="max-width:800px; margin:20px auto;">
    <form class="reanalysis-form" method="post" action="{{ url_for('reanalyze') }}" onsubmit="showLoading()" style="text-align:left;">
      <h3>Reanalyze</h3>
      <label>Choose Analysis Method:</label><br>
      <select name="analysis_method" id="analysisSelectRe">
        <option value="" disabled selected>Select method</option>
        <option value="shewhart">Shewhart</option>
        <option value="ewma">EWMA</option>
        <option value="mc-ewma">MC-EWMA</option>
        <option value="cusum" disabled style="color: gray;">CUSUM</option>
        <option value="scan" disabled style="color: gray;">SCAN</option>
      </select><br><br>
      <div id="lambdaInputRe" style="display:none;">
        <label>Choose your lambda option:</label><br>
        <select name="lam_option" id="lam_option_re">
          <option value="" disabled selected>Select option</option>
          <option value="manual">Manual</option>
          <option value="optimized">Optimized</option>
        </select><br><br>
        <div id="manualLambdaRe" style="display:none;">
          <label>Enter your lambda value (0 &lt; lambda &lt; 1):</label><br>
          <input type="number" step="any" name="lambda_val" id="lambda_val_re"><br><br>
        </div>
        <div id="sigmaInputRe" style="display:none;">
          <label>Enter sigma multiplier:</label><br>
          <input type="number" step="any" name="sigma_multiplier_re"><br><br>
        </div>
      </div>
      <input type="submit" value="Reanalyze">
    </form>
  </div>
  <!-- Clear Charts Button -->
  <div class="clear-container" style="max-width:800px; margin:20px auto; text-align:center;">
    <form action="{{ url_for('clear') }}" method="post" onsubmit="showLoading()">
      <input type="submit" value="Clear Charts">
    </form>
  </div>
  {% endif %}
  
  <hr>
  <div id="results">
    {% for result in results %}
      <div class="chart">
        <h3>{{ result.title }}</h3>
        <img src="data:image/png;base64,{{ result.image }}" />
      </div>
    {% endfor %}
  </div>
  
  <script>
    function showLoading() { 
      document.getElementById("loading").style.display = "block"; 
    }
    document.getElementById('behaviorSelect').addEventListener('change', function(){
      var val = this.value;
      document.getElementById('stableInputs').style.display = (val === 'stable') ? 'block' : 'none';
      document.getElementById('trendingInputs').style.display = (val === 'trending') ? 'block' : 'none';
      document.getElementById('periodicInputs').style.display = (val === 'periodic') ? 'block' : 'none';
    });
    document.querySelector('select[name="induce_change"]').addEventListener('change', function(){
      document.getElementById('changeInputs').style.display = (this.value.toLowerCase() === 'yes') ? 'block' : 'none';
    });
    document.getElementById('changeTypeSelect').addEventListener('change', function(){
      var val = this.value;
      document.getElementById('stepChange').style.display = (val === 'step') ? 'block' : 'none';
      document.getElementById('trendingChange').style.display = (val === 'trending') ? 'block' : 'none';
    });
    document.getElementById('analysisSelect').addEventListener('change', function(){
      var val = this.value;
      document.getElementById('lambdaInput').style.display = (val === 'ewma' || val === 'mc-ewma') ? 'block' : 'none';
    });
    document.querySelector('select[name="lam_option"]').addEventListener('change', function(){
      document.getElementById('manualLambda').style.display = (this.value.toLowerCase() === 'manual') ? 'block' : 'none';
    });
    // Reanalysis form events
    document.getElementById('analysisSelectRe').addEventListener('change', function(){
      var val = this.value;
      document.getElementById('lambdaInputRe').style.display = (val === 'ewma' || val === 'mc-ewma') ? 'block' : 'none';
      document.getElementById('sigmaInputRe').style.display = (val === 'ewma' || val === 'mc-ewma') ? 'block' : 'none';
    });
    document.getElementById('lam_option_re').addEventListener('change', function(){
      document.getElementById('manualLambdaRe').style.display = (this.value.toLowerCase() === 'manual') ? 'block' : 'none';
    });
  </script>
</body>
</html>
"""

# ---------------------------
# Instructions Template
# ---------------------------
instructions_template = """
<!DOCTYPE html>
<html>
<head>
  <title>Wastewatch - Instructions</title>
  <style>
    * { box-sizing: border-box; }
    body { background-color: #e0f7fa; font-family: Arial, sans-serif; margin: 20px; }
    h1, h2 { text-align: center; }
    .menu-box { margin-bottom: 20px; }
    .content { max-width: 800px; margin: 0 auto; background-color: #fff; padding: 20px; border-radius: 8px; }
    a { text-decoration: none; color: #007BFF; }
    .note { font-style: italic; color: #555; }
  </style>
</head>
<body>
  <h1>Wastewatch</h1>
  {{ nav_bar|safe }}
  <div class="content">
    <h2>Instructions</h2>
    <p>
      Welcome to Wastewatch – a simulation-based tool for evaluating statistical methods for detecting changes in wastewater data.
      This tool is designed to help you understand how different surveillance methods (such as Shewhart, EWMA, and MC-EWMA charts) perform in detecting significant changes that may be associated with epidemics.
    </p>
    <h3>How to Use Wastewatch</h3>
    <ol>
      <li>
        <strong>Baseline Data:</strong> Choose the behavior type for your baseline data.
        <ul>
          <li><em>Stable:</em> Data generated using a fixed mean and standard deviation. You can choose between a normal or lognormal distribution.</li>
          <li><em>Trending:</em> Data with a linear trend plus noise. Provide a starting value, slope, and noise level.</li>
          <li><em>Periodic:</em> Data that fluctuates periodically. Provide the mean, amplitude, period, and noise level.</li>
        </ul>
      </li>
      <li>
        <strong>Inducing a Change:</strong> Optionally, you can induce a change (simulating an epidemic) in the data.
        <ul>
          <li><em>Step Change:</em> The data’s mean is multiplied by a given factor starting on a specified day.</li>
          <li><em>Trending Change:</em> A new trend (with its own slope) is added for a specified duration.</li>
        </ul>
      </li>
      <li>
        <strong>Surveillance Method:</strong> Choose the analysis method.
        <ul>
          <li><em>Shewhart:</em> Monitors individual data points using control limits.</li>
          <li><em>EWMA:</em> Uses an Exponentially Weighted Moving Average, which incorporates a lambda value to weight recent observations.</li>
          <li><em>MC-EWMA:</em> A variation of EWMA where the center line is updated differently. You can also choose to optimize lambda here.</li>
        </ul>
        For EWMA and MC-EWMA, you have the option to enter a lambda value manually or use the "optimized" setting, which automatically finds the lambda value that minimizes the squared residual error over the baseline period.
      </li>
      <li>
        <strong>Simulation Parameters:</strong> Specify the number of days for the baseline data, the number of replications, and the sigma multiplier (used to set the control limits).
      </li>
      <li>
        <strong>Important Note:</strong> The change day must always be greater than the number of days used for baseline data.
      </li>
      <li>
        <strong>Analyze:</strong> Click the "Analyze" button to run the simulation. The results page will display control charts for several replications, a histogram of run lengths, and key performance metrics.
      </li>
      <li>
        <strong>Reanalyze:</strong> Use the reanalysis form to adjust parameters or change the analysis method without re-entering all of the baseline settings.
      </li>
    </ol>
    <p>
      Use the navigation links above to return to the main simulation page or to revisit these instructions.
    </p>
  </div>
</body>
</html>
"""

# ---------------------------
# Simulation Functions (including optimize_lambda)
# ---------------------------
def generate_behavior_data_sim(behavior, params, n_baseline):
    x = np.arange(n_baseline)
    if behavior == 'stable':
        dt = params.get('distribution_type', 'normal')
        if dt == 'normal':
            data = np.random.normal(loc=params['mean'], scale=params['std'], size=n_baseline)
        elif dt == 'lognormal':
            m = params['mean']
            s = params['std']
            std_log = np.sqrt(np.log(1 + (s**2) / (m**2)))
            mu_log = np.log(m) - 0.5 * std_log**2
            data = np.random.lognormal(mean=mu_log, sigma=std_log, size=n_baseline)
        else:
            raise ValueError("Unsupported distribution type for stable behavior!")
    elif behavior == 'trending':
        noise = params.get('noise', 1.0)
        data = params['start'] + params['slope'] * x + np.random.normal(scale=noise, size=n_baseline)
    elif behavior == 'periodic':
        noise = params.get('noise', 1.0)
        data = params['mean'] + params['amplitude'] * np.sin(2 * np.pi * x / params['period']) + np.random.normal(scale=noise, size=n_baseline)
    else:
        raise ValueError("Unsupported behavior type!")
    return list(data)

def calculate_limits_sim(data, sigma_multiplier, analysis_method="shewhart", lambda_val=0.3):
    mean = np.mean(data)
    if analysis_method == "mc-ewma":
        n = len(data)
        mc_ewma = np.zeros(n)
        mc_ewma[0] = mean
        for i in range(1, n):
            mc_ewma[i] = lambda_val * data[i-1] + (1 - lambda_val) * mc_ewma[i-1]
        residuals = np.array(data) - mc_ewma
        MR = np.abs(np.diff(residuals))
    else:
        MR = np.abs(np.diff(data))
    MR_bar = np.mean(MR) if len(MR) > 0 else 0
    sigma = MR_bar / 1.128
    return (mean - sigma_multiplier * sigma, mean + sigma_multiplier * sigma), \
           (mean - (sigma_multiplier - 1) * sigma, mean + (sigma_multiplier - 1) * sigma), mean, sigma

def apply_change_sim(data, change, change_day, params, original_behavior, baseline_mean, sigma, analysis_method, sigma_multiplier, baseline_period, lambda_val):
    max_days = 10000
    noise_val = params.get('noise', 1.0)
    std = params.get('std', None)
    if original_behavior == 'periodic':
        period = params.get('period', 50)
        amplitude = params.get('amplitude', 10)
    elif original_behavior == 'trending':
        slope = params.get('slope', 0.1)
        start = params['start']
    while len(data) < baseline_period:
        idx = len(data)
        if original_behavior == 'stable':
            new_value = np.random.normal(loc=baseline_mean, scale=std)
        elif original_behavior == 'periodic':
            cycle = idx % period
            new_value = baseline_mean + amplitude * np.sin(2*np.pi*cycle/period) + np.random.normal(scale=noise_val)
        elif original_behavior == 'trending':
            new_value = np.random.normal(loc=start + slope * idx, scale=noise_val)
        data.append(new_value)
    starting_value = data[change_day - 1] if (original_behavior=='trending' and change and change_day) else None
    step_change_done = False
    new_intercept = None
    out_of_control_index = None
    ewma_current = baseline_mean
    if analysis_method == 'mc-ewma':
        mc_ewma_list = [baseline_mean]
    while len(data) < max_days:
        idx = len(data)
        if change and idx >= (change_day if change_day is not None else baseline_period):
            if change['type'] == 'step':
                factor = change['factor']
                if original_behavior == 'stable':
                    new_value = np.random.normal(loc=baseline_mean * factor, scale=std)
                elif original_behavior == 'periodic':
                    cycle = idx % period
                    new_value = np.random.normal(loc=baseline_mean * factor, scale=noise_val) + amplitude * np.sin(2*np.pi*cycle/period)
                elif original_behavior == 'trending':
                    if not step_change_done:
                        new_intercept = np.mean(data[-min(5, len(data)):]) * factor
                        step_change_done = True
                    new_value = np.random.normal(loc=new_intercept + slope * (idx - change_day), scale=noise_val)
            elif change['type'] == 'trending':
                added_slope = change['slope']
                duration = change['duration']
                trend_index = idx - change_day
                if trend_index < duration:
                    if original_behavior == 'stable':
                        new_value = np.random.normal(loc=baseline_mean + added_slope * trend_index, scale=std)
                    elif original_behavior == 'periodic':
                        cycle = idx % period
                        new_value = np.random.normal(loc=baseline_mean + added_slope * trend_index, scale=noise_val) + amplitude * np.sin(2*np.pi*cycle/period)
                    elif original_behavior == 'trending':
                        new_value = np.random.normal(loc=starting_value + added_slope * trend_index, scale=noise_val)
                else:
                    if original_behavior == 'stable':
                        new_value = np.random.normal(loc=baseline_mean + added_slope * duration, scale=std)
                    elif original_behavior == 'periodic':
                        cycle = idx % period
                        new_value = np.random.normal(loc=baseline_mean + added_slope * duration, scale=noise_val) + amplitude * np.sin(2*np.pi*cycle/period)
                    elif original_behavior == 'trending':
                        new_value = np.random.normal(loc=starting_value + added_slope * duration + slope * (idx - (change_day + duration)), scale=noise_val)
        else:
            if original_behavior == 'stable':
                new_value = np.random.normal(loc=baseline_mean, scale=std)
            elif original_behavior == 'periodic':
                cycle = idx % period
                new_value = baseline_mean + amplitude * np.sin(2*np.pi*cycle/period) + np.random.normal(scale=noise_val)
            elif original_behavior == 'trending':
                if change and change['type'] == 'step' and step_change_done:
                    new_value = np.random.normal(loc=new_intercept + slope * (idx - change_day), scale=noise_val)
                else:
                    new_value = np.random.normal(loc=start + slope * idx, scale=noise_val)
        data.append(new_value)
        if len(data) > baseline_period:
            i = len(data) - 1
            if analysis_method == 'shewhart':
                if new_value > baseline_mean + sigma_multiplier * sigma or new_value < baseline_mean - sigma_multiplier * sigma:
                    out_of_control_index = i
                    break
            elif analysis_method == 'ewma':
                ewma_current = lambda_val * new_value + (1 - lambda_val) * ewma_current
                sigma_ewma = sigma * np.sqrt(lambda_val/(2 - lambda_val) * (1 - (1 - lambda_val)**(2 * i)))
                if ewma_current > baseline_mean + sigma_multiplier * sigma_ewma or ewma_current < baseline_mean - sigma_multiplier * sigma_ewma:
                    out_of_control_index = i
                    break
            elif analysis_method == 'mc-ewma':
                k = len(mc_ewma_list)
                mc_current = lambda_val * data[-2] + (1 - lambda_val) * mc_ewma_list[-1]
                mc_ewma_list.append(mc_current)
                if new_value > mc_current + sigma_multiplier * sigma or new_value < mc_current - sigma_multiplier * sigma:
                    out_of_control_index = i
                    break
    return data, out_of_control_index

def analyze_data_sim(data, control_limits, warning_limits, baseline_mean, sigma, out_of_control_index, change_day, analysis_method, sigma_multiplier, baseline_period, lambda_val):
    plt.figure(figsize=(10, 5))
    if change_day is not None:
        plt.axvline(change_day, color="purple", linestyle="dotted", label="Change Day", zorder=2)
    marker_value = None
    if analysis_method == "shewhart":
        plt.plot(data, label="Data", zorder=1)
        plt.axhline(baseline_mean, color="green", label="Center Line (X̄)", zorder=2)
        plt.axhline(baseline_mean + sigma_multiplier * sigma, color="red", linestyle="dashed", label="Upper Control Limit", zorder=2)
        plt.axhline(baseline_mean - sigma_multiplier * sigma, color="red", linestyle="dashed", label="Lower Control Limit", zorder=2)
        plt.axhline(baseline_mean + (sigma_multiplier - 1) * sigma, color="orange", linestyle="dashed", label="Upper Warning Limit", zorder=2)
        plt.axhline(baseline_mean - (sigma_multiplier - 1) * sigma, color="orange", linestyle="dashed", label="Lower Warning Limit", zorder=2)
        plt.title("Shewhart Chart")
        marker_value = data[out_of_control_index] if out_of_control_index is not None else None
    elif analysis_method == "ewma":
        n = len(data)
        ewma = np.zeros(n); ewma[0] = baseline_mean
        ucl = np.zeros(n); lcl = np.zeros(n)
        for i in range(1, n):
            ewma[i] = lambda_val * data[i] + (1 - lambda_val) * ewma[i-1]
        for i in range(n):
            sigma_ewma = sigma * np.sqrt(lambda_val/(2 - lambda_val) * (1 - (1 - lambda_val)**(2*i)))
            ucl[i] = baseline_mean + sigma_multiplier * sigma_ewma
            lcl[i] = baseline_mean - sigma_multiplier * sigma_ewma
        plt.plot(ewma, color="green", zorder=2, label="EWMA")
        plt.plot(ucl, color="red", linestyle="dashed", zorder=2, label="Upper EWMA CL")
        plt.plot(lcl, color="red", linestyle="dashed", zorder=2, label="Lower EWMA CL")
        plt.title(f"EWMA Chart (λ = {lambda_val:.3f}".rstrip('0').rstrip('.') + f", {sigma_multiplier}σ)")
        marker_value = ewma[out_of_control_index] if out_of_control_index is not None else None
    elif analysis_method == "mc-ewma":
        n = len(data)
        mc_ewma = np.zeros(n); mc_ewma[0] = baseline_mean
        ucl = np.zeros(n); lcl = np.zeros(n)
        for i in range(1, n):
            mc_ewma[i] = lambda_val * data[i-1] + (1 - lambda_val) * mc_ewma[i-1]
        for i in range(n):
            ucl[i] = mc_ewma[i] + sigma_multiplier * sigma
            lcl[i] = mc_ewma[i] - sigma_multiplier * sigma
        plt.plot(mc_ewma, color="green", zorder=2, label="MC-EWMA")
        plt.plot(ucl, color="red", linestyle="dashed", zorder=2, label="Upper MC-EWMA CL")
        plt.plot(lcl, color="red", linestyle="dashed", zorder=2, label="Lower MC-EWMA CL")
        formatted_lambda = format(lambda_val, '.3f').rstrip('0').rstrip('.')
        plt.title(f"MC-EWMA Chart (λ = {formatted_lambda}, {sigma_multiplier}σ)")
        marker_value = data[out_of_control_index] if out_of_control_index is not None else None

    if out_of_control_index is not None:
        run_length = (out_of_control_index - baseline_period) + 1
        plt.scatter(out_of_control_index, marker_value, color="red", s=100, zorder=3, label=f"Out-of-Control (RL: {run_length})")
    plt.legend()
    plt.tight_layout()
     
def plot_replicates_and_histogram(replications, run_lengths, change_day, analysis_method, sigma_multiplier, baseline_period, n_replications,
                                  arl_value, metric_label, avg_sigma, avg_change_day, limit_stopped_percentage, lambda_val):
    fig = plt.figure(figsize=(14, 8))
    gs = fig.add_gridspec(nrows=2, ncols=3, width_ratios=[0.8, 1, 3])
    
    # Legend in Column 0
    legend_ax = fig.add_subplot(gs[:, 0])
    legend_ax.axis("off")
    if analysis_method == "shewhart":
        handles = [
            Line2D([0], [0], color="blue", lw=2, label="Simulated Data"),
            Line2D([0], [0], color="green", lw=2, label="Center Line (X̄)"),
            Line2D([0], [0], color="red", lw=2, linestyle="dashed", label="Upper CL"),
            Line2D([0], [0], color="red", lw=2, linestyle="dashed", label="Lower CL"),
            Line2D([0], [0], color="orange", lw=2, linestyle="dashed", label="Upper Warning"),
            Line2D([0], [0], color="orange", lw=2, linestyle="dashed", label="Lower Warning"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="red", markersize=10, label="Out-of-Control")
        ]
    elif analysis_method == "ewma":
        handles = [
            Line2D([0], [0], color="blue", lw=2, label="Simulated Data"),
            Line2D([0], [0], color="green", lw=2, label="EWMA"),
            Line2D([0], [0], color="red", lw=2, linestyle="dashed", label="Upper EWMA CL"),
            Line2D([0], [0], color="red", lw=2, linestyle="dashed", label="Lower EWMA CL"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="red", markersize=10, label="Out-of-Control")
        ]
    elif analysis_method == "mc-ewma":
        handles = [
            Line2D([0], [0], color="blue", lw=2, label="Simulated Data"),
            Line2D([0], [0], color="green", lw=2, label="MC-EWMA"),
            Line2D([0], [0], color="red", lw=2, linestyle="dashed", label="Upper MC-EWMA CL"),
            Line2D([0], [0], color="red", lw=2, linestyle="dashed", label="Lower MC-EWMA CL"),
            Line2D([0], [0], marker="o", color="w", markerfacecolor="red", markersize=10, label="Out-of-Control")
        ]
    else:
        handles = []
    legend_ax.legend(handles=handles, loc="center")
    
    # Replication plots in Column 1
    rep_positions = [(0, 1), (1, 1)]
    for idx, pos in enumerate(rep_positions):
        if idx < len(replications):
            ax = fig.add_subplot(gs[pos[0], pos[1]])
            data, out_idx, _, _, baseline_mean, sigma = replications[idx]
            ax.plot(data, color="blue", zorder=1)
            if change_day is not None:
                ax.axvline(change_day, color="purple", linestyle="dotted", zorder=2)
            rl = (replications[idx][1] - baseline_period + 1) if replications[idx][1] is not None else "∞"
            ax.set_title(f"Replication {idx+1} (RL: {rl})")
            if analysis_method == "shewhart":
                ax.axhline(baseline_mean, color="green", zorder=2)
                ax.axhline(baseline_mean + sigma_multiplier * sigma, color="red", linestyle="dashed", zorder=2)
                ax.axhline(baseline_mean - sigma_multiplier * sigma, color="red", linestyle="dashed", zorder=2)
                ax.axhline(baseline_mean + (sigma_multiplier - 1) * sigma, color="orange", linestyle="dashed", zorder=2)
                ax.axhline(baseline_mean - (sigma_multiplier - 1) * sigma, color="orange", linestyle="dashed", zorder=2)
            elif analysis_method == "ewma":
                n = len(data)
                ewma = np.zeros(n)
                ewma[0] = baseline_mean
                ucl = np.zeros(n)
                lcl = np.zeros(n)
                for i in range(1, n):
                    ewma[i] = lambda_val * data[i] + (1 - lambda_val) * ewma[i-1]
                for i in range(n):
                    sigma_ewma = sigma * np.sqrt(lambda_val/(2 - lambda_val) * (1 - (1 - lambda_val)**(2*i)))
                    ucl[i] = baseline_mean + sigma_multiplier * sigma_ewma
                    lcl[i] = baseline_mean - sigma_multiplier * sigma_ewma
                ax.plot(ewma, color="green", zorder=2)
                ax.plot(ucl, color="red", linestyle="dashed", zorder=2)
                ax.plot(lcl, color="red", linestyle="dashed", zorder=2)
            elif analysis_method == "mc-ewma":
                n = len(data)
                mc_ewma = np.zeros(n)
                mc_ewma[0] = baseline_mean
                ucl = np.zeros(n)
                lcl = np.zeros(n)
                for i in range(1, n):
                    mc_ewma[i] = lambda_val * data[i-1] + (1 - lambda_val) * mc_ewma[i-1]
                for i in range(n):
                    ucl[i] = mc_ewma[i] + sigma_multiplier * sigma
                    lcl[i] = mc_ewma[i] - sigma_multiplier * sigma
                ax.plot(mc_ewma, color="green", zorder=2)
                ax.plot(ucl, color="red", linestyle="dashed", zorder=2)
                ax.plot(lcl, color="red", linestyle="dashed", zorder=2)
            if out_idx is not None:
                marker = ewma[out_idx] if analysis_method=="ewma" else data[out_idx]
                ax.scatter(out_idx, marker, color="red", s=100, zorder=3)
    
    # Histogram and Text Box in Column 2
    outer_ax = fig.add_subplot(gs[:, 2])
    outer_ax.axis("off")
    inner_gs = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=gs[:, 2], width_ratios=[4, 1])
    hist_ax = fig.add_subplot(inner_gs[0])
    text_ax = fig.add_subplot(inner_gs[1])
    
    run_arr = np.array(run_lengths)
    unique_vals = np.unique(run_arr)
    if len(unique_vals) <= 10:
        bins = np.concatenate(([unique_vals[0]-0.5], unique_vals+0.5))
    else:
        bins = int(np.ceil(np.sqrt(n_replications)))
    hist_ax.hist(run_arr, bins=bins, edgecolor="black")
    hist_ax.set_title("Histogram of Run Lengths")
    hist_ax.set_xlabel("Run Length")
    hist_ax.set_ylabel("Frequency")
    
    stats = (f"Replications: {n_replications}\nMin: {run_arr.min():.2f}\nMedian: {np.median(run_arr):.2f}\nMax: {run_arr.max():.2f}\nARL: {arl_value:.2f}\n")
    if metric_label=="FAR":
        stats += f"FAR: {1/arl_value:.4f}\n"
    stats += f"Avg Sigma: {avg_sigma:.2f}\nChange Day: {int(avg_change_day) if avg_change_day is not None else 'N/A'}\nStopped at 10000: {limit_stopped_percentage:.2f}%"
    text_ax.text(0.05, 0.95, stats, transform=text_ax.transAxes, verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
    text_ax.axis("off")
    
    plt.tight_layout()
    
def optimize_lambda(baseline_data, method):
    """
    Optimize lambda by brute force over the baseline data.
    For each lambda value between 0.01 and 0.99, compute the EWMA or MC-EWMA series
    (depending on method) and sum the squared residuals between the series and the data.
    Returns the lambda that minimizes the error.
    """
    best_lambda = 0
    best_error = float('inf')
    baseline_data = np.array(baseline_data)
    n = len(baseline_data)
    
    for lam in np.arange(0.01, 1.0, 0.01):
        series = np.zeros(n)
        series[0] = baseline_data[0]
        if method == "ewma":
            for i in range(1, n):
                series[i] = lam * baseline_data[i] + (1 - lam) * series[i-1]
        elif method == "mc-ewma":
            for i in range(1, n):
                series[i] = lam * baseline_data[i-1] + (1 - lam) * series[i-1]
        else:
            for i in range(1, n):
                series[i] = lam * baseline_data[i] + (1 - lam) * series[i-1]
        residuals = baseline_data - series
        total_error = np.sum(residuals**2)
        if total_error < best_error:
            best_error = total_error
            best_lambda = lam
    return best_lambda, best_error

def run_simulation(behavior, params, n_baseline, change, change_day, analysis_method, n_replications, sigma_multiplier, max_days, lambda_val):
    baseline_period = change_day if (change and change_day is not None) else n_baseline
    run_lengths = []
    replications = []
    sigmas = []
    change_days = []
    for _ in range(n_replications):
        data = generate_behavior_data_sim(behavior, params, n_baseline)
        _, _, baseline_mean, sigma = calculate_limits_sim(data, sigma_multiplier, analysis_method, lambda_val)
        sigmas.append(sigma)
        data, out_idx = apply_change_sim(data, change, change_day, params, behavior, baseline_mean, sigma, analysis_method, sigma_multiplier, baseline_period, lambda_val)
        if out_idx is not None:
            run_length = (out_idx - baseline_period) + 1
        else:
            run_length = (max_days - baseline_period) + 1
        run_lengths.append(run_length)
        replications.append((data, out_idx, None, None, baseline_mean, sigma))
        if change_day is not None:
            change_days.append(change_day)
    arl_value = np.mean(run_lengths) if run_lengths else float('inf')
    avg_sigma = np.mean(sigmas) if sigmas else 0
    avg_change_day = np.mean(change_days) if change_days else None
    limit_pct = (sum(1 for r in replications if r[1] is None) / n_replications) * 100
    metric_label = "FAR" if change is None else "ARL"
    
    formatted_lambda = format(lambda_val, '.3f').rstrip('0').rstrip('.')
    
    if analysis_method == "shewhart":
        chart_title = f"Shewhart Chart ({sigma_multiplier}σ)"
    elif analysis_method == "ewma":
        chart_title = f"EWMA Chart (λ = {formatted_lambda}, {sigma_multiplier}σ)"
    elif analysis_method == "mc-ewma":
        chart_title = f"MC-EWMA Chart (λ = {formatted_lambda}, {sigma_multiplier}σ)"
    else:
        chart_title = ""
    
    buf = io.BytesIO()
    plot_replicates_and_histogram(replications, run_lengths, change_day, analysis_method, sigma_multiplier, baseline_period, n_replications,
                                  arl_value, metric_label, avg_sigma, avg_change_day, limit_pct, lambda_val)
    plt.savefig(buf, format="png", dpi=80)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    plt.close()
    return img_base64, arl_value, chart_title

@app.route("/", methods=["GET", "POST"])
def index():
    global previous_results
    if request.method == "POST":
        # --------------------------
        # Step 1: Block if system is under load
        # --------------------------
        mem = psutil.virtual_memory().percent
        cpu = psutil.cpu_percent(interval=1)

        if mem > 85 or cpu > 85:
            return render_template_string(
                "<h2 style='color:red;text-align:center;'> System is under high load. Please try again later.</h2>" + main_template,
                results=previous_results,
                full_params_exists=('full_params' in session),
                nav_bar=nav_bar
            )

        # --------------------------
        # Step 2: Soft cap if replications too high under medium load
        # --------------------------
        n_replications_str = request.form.get("n_replications", "0")
        try:
            if int(n_replications_str) > 1000 and (mem > 70 or cpu > 70):
                return render_template_string(
                    "<h2 style='color:red;text-align:center;'> Too many replications while system is moderately loaded. Please try a smaller number.</h2>" + main_template,
                    results=previous_results,
                    full_params_exists=('full_params' in session),
                    nav_bar=nav_bar
                )
        except ValueError:
            pass  # fallback to error later if needed

        fd = request.form.to_dict()
        try:
            n_baseline = int(fd.get("n_baseline", "0"))
            n_replications = int(fd.get("n_replications", "0"))
            sigma_multiplier = float(fd.get("sigma_multiplier", "0"))
        except ValueError:
            n_baseline = n_replications = sigma_multiplier = 0
        behavior = fd.get("behavior")
        if behavior == "stable":
            params = {"mean": float(fd.get("mean", "0")), "std": float(fd.get("std", "0")), "distribution_type": fd.get("dist_type", "normal")}
        elif behavior == "trending":
            params = {"start": float(fd.get("start", "0")), "slope": float(fd.get("slope", "0")), "noise": float(fd.get("noise", "0"))}
        elif behavior == "periodic":
            params = {"mean": float(fd.get("p_mean", "0")), "amplitude": float(fd.get("amplitude", "0")), "period": int(fd.get("period", "50")), "noise": float(fd.get("p_noise", "0"))}
        else:
            params = {}
        induce = fd.get("induce_change", "no").lower() == "yes"
        if induce:
            change_day = int(fd.get("change_day", "0"))
            ct = fd.get("change_type", "")
            if ct == "step":
                factor = float(fd.get("factor", "0")) if fd.get("factor", "").strip() else None
                change = {"type": "step", "factor": factor}
            elif ct == "trending":
                cs = float(fd.get("change_slope", "0")) if fd.get("change_slope", "").strip() else None
                td = int(fd.get("trend_duration", "0")) if fd.get("trend_duration", "").strip() else None
                change = {"type": "trending", "slope": cs, "duration": td}
            else:
                change = None
        else:
            change = None
            change_day = None
        analysis_method = fd.get("analysis_method")
        if analysis_method not in ["shewhart", "ewma", "mc-ewma"]:
            analysis_method = "shewhart"
            lambda_val = 0.3
        else:
            if analysis_method in ["ewma", "mc-ewma"]:
                lam_option = fd.get("lam_option", "").strip().lower()
                if lam_option == "manual":
                    lambda_val = float(fd.get("lambda_val", "0.3"))
                elif lam_option == "optimized":
                    baseline_data = generate_behavior_data_sim(behavior, params, n_baseline)
                    lambda_val, _ = optimize_lambda(np.array(baseline_data), method=analysis_method)
                else:
                    lambda_val = 0.3
            else:
                lambda_val = 0.3
        session['full_params'] = {"behavior": behavior, "params": params, "n_baseline": n_baseline,
                                  "n_replications": n_replications, "sigma_multiplier": sigma_multiplier,
                                  "change": change, "change_day": change_day, "max_days": 10000}
        img, arl_value, chart_title = run_simulation(behavior, params, n_baseline, change, change_day,
                                                     analysis_method, n_replications, sigma_multiplier, 10000, lambda_val)
        previous_results.append({"image": img, "title": chart_title})
    return render_template_string(main_template, results=previous_results, full_params_exists=('full_params' in session), nav_bar=nav_bar)

@app.route("/instructions")
def instructions():
    return render_template_string(instructions_template, nav_bar=nav_bar)

@app.route("/clear", methods=["POST"])
def clear():
    global previous_results
    previous_results = []
    return redirect(url_for('index'))

@app.route("/reanalyze", methods=["GET", "POST"])
def reanalyze():
    if 'full_params' not in session:
        return redirect(url_for('index'))
    if request.method == "POST":
        analysis_method = request.form.get("analysis_method")
        if analysis_method not in ["shewhart", "ewma", "mc-ewma"]:
            analysis_method = "shewhart"
            lambda_val = 0.3
        else:
            if analysis_method in ["ewma", "mc-ewma"]:
                lam_option = request.form.get("lam_option", "").strip().lower()
                if lam_option == "manual":
                    lambda_val = float(request.form.get("lambda_val", "0.3"))
                elif lam_option == "optimized":
                    fp = session['full_params']
                    behavior, params = fp["behavior"], fp["params"]
                    n_baseline = fp["n_baseline"]
                    baseline_data = generate_behavior_data_sim(behavior, params, n_baseline)
                    lambda_val, _ = optimize_lambda(np.array(baseline_data), method=analysis_method)
                else:
                    lambda_val = 0.3
            else:
                lambda_val = 0.3
        sigma_multiplier = float(request.form.get("sigma_multiplier_re", "").strip() or session['full_params'].get("sigma_multiplier", 1))
        fp = session['full_params']
        behavior, params = fp["behavior"], fp["params"]
        n_baseline, n_replications = fp["n_baseline"], fp["n_replications"]
        change, change_day, max_days = fp["change"], fp["change_day"], fp["max_days"]
        
        img, arl_value, chart_title = run_simulation(behavior, params, n_baseline, change, change_day,
                                                     analysis_method, n_replications, sigma_multiplier, max_days, lambda_val)
        previous_results.append({"image": img, "title": chart_title})
        return redirect(url_for('index'))
    return render_template_string(reanalyze_template, nav_bar=nav_bar)

reanalyze_template = """
<!DOCTYPE html>
<html>
<head>
  <title>Wastewatch - Reanalyze</title>
  <style>
    body { background-color: #e0f7fa; font-family: Arial, sans-serif; margin: 20px; }
    h1 { text-align: center; }
    form.reanalysis-form { background-color: #fff; padding: 20px; border-radius: 8px; max-width: 800px; margin: 20px auto; line-height: 1.6; }
  </style>
</head>
<body>
  <h1>Wastewatch - Reanalyze</h1>
  {{ nav_bar|safe }}
  <div class="form-container" style="max-width:800px; margin:20px auto;">
    <form class="reanalysis-form" method="post" onsubmit="showLoading()">
      <label>Choose Analysis Method:</label><br>
      <select name="analysis_method" id="analysisSelectRe">
        <option value="" disabled selected>Select method</option>
        <option value="shewhart">Shewhart</option>
        <option value="ewma">EWMA</option>
        <option value="mc-ewma">MC-EWMA</option>
        <option value="cusum" disabled style="color: gray;">CUSUM</option>
        <option value="scan" disabled style="color: gray;">SCAN</option>
      </select><br><br>
      <div id="lambdaInputRe" style="display:none;">
        <label>Choose your lambda option:</label><br>
        <select name="lam_option" id="lam_option_re">
          <option value="" disabled selected>Select option</option>
          <option value="manual">Manual</option>
          <option value="optimized">Optimized</option>
        </select><br><br>
        <div id="manualLambdaRe" style="display:none;">
          <label>Enter your lambda value (0 &lt; lambda &lt; 1):</label><br>
          <input type="number" step="any" name="lambda_val" id="lambda_val_re"><br><br>
        </div>
        <div id="sigmaInputRe" style="display:none;">
          <label>Enter sigma multiplier:</label><br>
          <input type="number" step="any" name="sigma_multiplier_re"><br><br>
        </div>
      </div>
      <input type="submit" value="Reanalyze">
    </form>
  </div>
  <div class="clear-container" style="max-width:800px; margin:20px auto; text-align:center;">
    <form action="{{ url_for('clear') }}" method="post" onsubmit="showLoading()">
      <input type="submit" value="Clear Charts">
    </form>
  </div>
  <script>
    function showLoading() { document.getElementById("loading").style.display = "block"; }
    document.getElementById('analysisSelectRe').addEventListener('change', function(){
      var val = this.value;
      document.getElementById('lambdaInputRe').style.display = (val === 'ewma' || val === 'mc-ewma') ? 'block' : 'none';
      document.getElementById('sigmaInputRe').style.display = (val === 'ewma' || val === 'mc-ewma') ? 'block' : 'none';
    });
    document.getElementById('lam_option_re').addEventListener('change', function(){
      document.getElementById('manualLambdaRe').style.display = (this.value.toLowerCase() === 'manual') ? 'block' : 'none';
    });
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True)

document.addEventListener("DOMContentLoaded", function () {
    const regionSelect = document.getElementById("region");
    const output = document.getElementById("output");
  
    regionSelect.addEventListener("change", function () {
      const selectedRegion = regionSelect.value;
      output.textContent = `You selected: ${selectedRegion}`;
    });
  });
  
// NO <script> tags here! Just the code.

// Make sure these are strings (inside quotes "")
const SUPABASE_URL = "https://tcrecgfuztvidwqfjfsj.supabase.co"; 
const SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRjcmVjZ2Z1enR2aWR3cWZqZnNqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk0Mjg3ODMsImV4cCI6MjA4NTAwNDc4M30.4C696GSXbBwCg4djAKiMeMsxAPFeMN4z8gosROJ0y9A"; 

const supabaseClient = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

async function sendOtp() {
  const email = document.getElementById("email").value;
  if (!email) {
    alert("Please enter email");
    return;
  }
  
  localStorage.setItem("userEmail", email); // Save email for step 2

  const { error } = await supabaseClient.auth.signInWithOtp({ email });

  if (error) {
    alert(error.message);
  } else {
    window.location.href = "/verify-otp"; 
  }
}

async function verifyOtp() {
  const otp = document.getElementById("otp").value;
  const email = localStorage.getItem("userEmail"); // Retrieve email

  if (!otp) return alert("Enter OTP");
  if (!email) return alert("Email missing");

  const { data, error } = await supabaseClient.auth.verifyOtp({
    email: email,
    token: otp,
    type: "email",
  });

  if (error) {
    alert(error.message);
  } else {
    localStorage.removeItem("userEmail");
    window.location.href = "/dashboard";
  }
}
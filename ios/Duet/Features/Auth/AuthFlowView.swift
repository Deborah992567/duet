import SwiftUI

/// Lightweight onboarding flow: Login → Register / Forgot password.
struct AuthFlowView: View {
    @State private var showingRegister = false
    @State private var showingForgot = false

    var body: some View {
        NavigationStack {
            LoginView()
                .navigationDestination(isPresented: $showingRegister) {
                    RegisterView()
                }
                .navigationDestination(isPresented: $showingForgot) {
                    ForgotPasswordView()
                }
        }
    }
}
import React from 'react';
import Head from 'next/head';

const NewClaimPage = () => {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <Head>
        <title>File a New Claim - CogniClaim</title>
        <meta name="description" content="File a new insurance claim with CogniClaim's AI-powered platform." />
      </Head>

      <div className="max-w-md w-full space-y-8 glassy-card p-10 rounded-lg shadow-lg">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-text-secondary">
            File a New Claim
          </h2>
          <p className="mt-2 text-center text-sm text-gray-400">
            Please fill out the form below to submit your claim.
          </p>
        </div>
        <form className="mt-8 space-y-6" action="#" method="POST">
          <div className="rounded-md shadow-sm -space-y-px">
            <div>
              <label htmlFor="claim-type" className="sr-only">Claim Type</label>
              <select
                id="claim-type"
                name="claim-type"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-600 placeholder-gray-500 text-base-100 bg-transparent focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm"
              >
                <option value="">Select Claim Type</option>
                <option value="auto">Auto Insurance</option>
                <option value="home">Home Insurance</option>
                <option value="health">Health Insurance</option>
                <option value="life">Life Insurance</option>
              </select>
            </div>
            <div className="pt-4">
              <label htmlFor="description" className="sr-only">Description</label>
              <textarea
                id="description"
                name="description"
                rows={4}
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-600 placeholder-gray-500 text-base-100 bg-transparent focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm"
                placeholder="Brief description of the incident..."
              ></textarea>
            </div>
            <div className="pt-4">
              <label htmlFor="date-of-incident" className="sr-only">Date of Incident</label>
              <input
                id="date-of-incident"
                name="date-of-incident"
                type="date"
                required
                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-600 placeholder-gray-500 text-base-100 bg-transparent focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm"
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-text-primary bg-primary hover:bg-primary-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              Submit Claim
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default NewClaimPage;
